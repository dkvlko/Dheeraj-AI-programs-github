import os
import glob
from google.cloud import vision

# Folder containing images
IMAGE_FOLDER = "/home/dkvlko/Dheeraj-AI-programs-github/liv_code/Data-Processing-ForMoodle-TABText/DATA-WIN11-NOTES-UPTGT/"

# Initialize Vision client (uses gcloud credentials automatically)
client = vision.ImageAnnotatorClient()

# Get all PNG files
image_files = sorted(glob.glob(os.path.join(IMAGE_FOLDER, "*.png")))

print(f"Found {len(image_files)} images")

for image_path in image_files:

    print(f"Processing: {image_path}")

    with open(image_path, "rb") as img_file:
        content = img_file.read()

    image = vision.Image(content=content)

    # Best OCR mode for documents
    response = client.document_text_detection(image=image)

    text = response.full_text_annotation.text

    # Save output text file
    txt_path = os.path.splitext(image_path)[0] + ".txt"

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(text)

    print(f"Saved: {txt_path}")

    if response.error.message:
        raise Exception(response.error.message)

print("\nOCR completed.")