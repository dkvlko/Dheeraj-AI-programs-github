
#!/usr/bin/env python3

import csv
import math
import re
from pathlib import Path

import cv2
import pytesseract
from pytesseract import Output


IMAGE_PATH = Path(
    "/home/dkvlko/Pictures/GMPics/GM-01-Test.png"
)

OUTPUT_CSV = IMAGE_PATH.with_name("GM-01-Test-ocr.csv")
OUTPUT_TXT = IMAGE_PATH.with_name("GM-01-Test-ocr.txt")

SCREEN_WIDTH = 1366
SCREEN_HEIGHT = 768

# Approximate glyph-height filter, in screenshot pixels.
# Tune these values after inspecting the first result.
MIN_TEXT_HEIGHT = 8
MAX_TEXT_HEIGHT = 22

# Smaller increments improve orientation coverage but take longer.
ANGLE_STEP = 15

MIN_CONFIDENCE = 35


def rotate_expanded(image, angle):
    """Rotate without clipping the original image."""
    h, w = image.shape[:2]
    center = (w / 2, h / 2)

    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)

    cos_a = abs(matrix[0, 0])
    sin_a = abs(matrix[0, 1])

    new_w = int(h * sin_a + w * cos_a)
    new_h = int(h * cos_a + w * sin_a)

    matrix[0, 2] += new_w / 2 - center[0]
    matrix[1, 2] += new_h / 2 - center[1]

    rotated = cv2.warpAffine(
        image,
        matrix,
        (new_w, new_h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(255, 255, 255),
    )

    return rotated, matrix


def transform_point(x, y, inverse_matrix):
    """Convert a rotated-image point to original-image coordinates."""
    ox = inverse_matrix[0, 0] * x
    ox += inverse_matrix[0, 1] * y + inverse_matrix[0, 2]

    oy = inverse_matrix[1, 0] * x
    oy += inverse_matrix[1, 1] * y + inverse_matrix[1, 2]

    return ox, oy


def normalize_text(text):
    return re.sub(r"\s+", " ", text).strip().casefold()


def iou(a, b):
    """Intersection over union of two axis-aligned boxes."""
    ax, ay, aw, ah = a["x"], a["y"], a["width"], a["height"]
    bx, by, bw, bh = b["x"], b["y"], b["width"], b["height"]

    left = max(ax, bx)
    top = max(ay, by)
    right = min(ax + aw, bx + bw)
    bottom = min(ay + ah, by + bh)

    intersection = max(0, right - left) * max(0, bottom - top)
    union = aw * ah + bw * bh - intersection

    return intersection / union if union else 0.0


def same_detection(a, b):
    if normalize_text(a["text"]) != normalize_text(b["text"]):
        return False

    if iou(a, b) >= 0.30:
        return True

    # A rotated bounding box may differ in size between scans.
    acx = a["x"] + a["width"] / 2
    acy = a["y"] + a["height"] / 2
    bcx = b["x"] + b["width"] / 2
    bcy = b["y"] + b["height"] / 2

    distance = math.hypot(acx - bcx, acy - bcy)
    tolerance = max(5, min(a["height"], b["height"]))

    return distance <= tolerance


def main():
    if not IMAGE_PATH.is_file():
        raise FileNotFoundError(IMAGE_PATH)

    image = cv2.imread(str(IMAGE_PATH))
    if image is None:
        raise RuntimeError(f"Cannot read image: {IMAGE_PATH}")

    original_h, original_w = image.shape[:2]

    print(f"Image dimensions: {original_w} x {original_h}")

    # Screenshot pixels map to the requested coordinate system.
    scale_x = SCREEN_WIDTH / original_w
    scale_y = SCREEN_HEIGHT / original_h

    candidates = []

    angles = list(range(0, 180, ANGLE_STEP))

    for index, angle in enumerate(angles, start=1):
        print(f"Scanning angle {angle}° ({index}/{len(angles)})")

        rotated, matrix = rotate_expanded(image, angle)
        inverse_matrix = cv2.invertAffineTransform(matrix)

        # PSM 11 detects sparse text in different screen regions.
        data = pytesseract.image_to_data(
            rotated,
            lang="eng",
            config="--oem 3 --psm 11",
            output_type=Output.DICT,
        )

        for i, raw_text in enumerate(data["text"]):
            text = re.sub(r"\s+", " ", raw_text).strip()

            if not text or not re.search(r"[A-Za-z]", text):
                continue

            try:
                confidence = float(data["conf"][i])
            except (ValueError, TypeError):
                continue

            if confidence < MIN_CONFIDENCE:
                continue

            # Tesseract supplies a word box in the rotated image.
            rx = int(data["left"][i])
            ry = int(data["top"][i])
            rw = int(data["width"][i])
            rh = int(data["height"][i])

            if rh < MIN_TEXT_HEIGHT or rh > MAX_TEXT_HEIGHT:
                continue

            # Transform all four corners to the original image.
            corners = [
                transform_point(rx, ry, inverse_matrix),
                transform_point(rx + rw, ry, inverse_matrix),
                transform_point(rx, ry + rh, inverse_matrix),
                transform_point(rx + rw, ry + rh, inverse_matrix),
            ]

            xs = [p[0] for p in corners]
            ys = [p[1] for p in corners]

            # Axis-aligned bounding box in the original image.
            x1 = max(0, min(original_w, math.floor(min(xs))))
            y1 = max(0, min(original_h, math.floor(min(ys))))
            x2 = max(0, min(original_w, math.ceil(max(xs))))
            y2 = max(0, min(original_h, math.ceil(max(ys))))

            if x2 <= x1 or y2 <= y1:
                continue

            # Map to 1366 x 768 screenshot coordinates.
            x = round(x1 * scale_x)
            y = round(y1 * scale_y)
            width = round((x2 - x1) * scale_x)
            height = round((y2 - y1) * scale_y)

            candidates.append({
                "text": text,
                "x": x,
                "y": y,
                "width": width,
                "height": height,
                "confidence": round(confidence, 1),
                "scan_angle": angle,
                "_glyph_height": rh,
            })

    # Prefer higher-confidence detections and suppress duplicates.
    candidates.sort(key=lambda d: d["confidence"], reverse=True)

    results = []

    for candidate in candidates:
        if any(same_detection(candidate, old) for old in results):
            continue
        results.append(candidate)

    # Reading order: top to bottom, then left to right.
    results.sort(key=lambda d: (d["y"], d["x"]))

    fields = [
        "text", "x", "y", "width", "height",
        "confidence", "scan_angle",
    ]

    with OUTPUT_CSV.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()

        for result in results:
            writer.writerow({
                key: result[key] for key in fields
            })

    with OUTPUT_TXT.open("w", encoding="utf-8") as f:
        for result in results:
            f.write(
                f'({result["x"]}, {result["y"]}) '
                f'{result["text"]}\n'
            )

    print(f"\nUnique text detections: {len(results)}")
    print(f"CSV output: {OUTPUT_CSV}")
    print(f"Text output: {OUTPUT_TXT}")

    for result in results:
        print(
            f'({result["x"]:4}, {result["y"]:4}) '
            f'{result["text"]} '
            f'[confidence={result["confidence"]}]'
        )


if __name__ == "__main__":
    main()

