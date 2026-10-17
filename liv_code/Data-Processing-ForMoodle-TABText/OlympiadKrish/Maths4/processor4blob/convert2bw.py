from PIL import Image
import sys
from pathlib import Path

def main():
    # Input and output paths

    input_path = "/home/dkvlko/Dheeraj-AI-programs-github/liv_code/BLOBS/Priyanka-Idioms-Phrases"

    # One level up
    INPUT_DIR = Path(input_path)

    # Images are inside INPUT_DIR/SPLIT
    IMAGE_DIR = INPUT_DIR 

    # OUTPUT_DIR = INPUT_DIR/SPLIT_2_TEXT
    OUTPUT_DIR = INPUT_DIR / "REMWATERM"

    # Create OUTPUT_DIR if not present
    OUTPUT_DIR.mkdir(exist_ok=True)

    #print(f"SCRIPT_DIR  : {SCRIPT_DIR}")
    print(f"INPUT_DIR   : {INPUT_DIR}")
    print(f"IMAGE_DIR   : {IMAGE_DIR}")
    print(f"OUTPUT_DIR  : {OUTPUT_DIR}")
    print("--------------------------------------------------")

    if not IMAGE_DIR.exists():
        print("SPLIT directory does not exist.")
        sys.exit(1)

    # Load all PNG images containing token
    images = sorted(
        IMAGE_DIR.glob("Idioms*.png")
    )

    if not images:
        print("No matching PNG images found.")
        sys.exit(0)

    print(f"Found {len(images)} images to process.\n")

    # Process each image
    for img_path in images:
        print(f"Processing: {img_path.name}")
        try:

            # Open image and ensure RGB mode
            img = Image.open(img_path).convert("RGB")

            # Get pixel data
            pixels = img.load()

            width, height = img.size

            threshold = 128  # adjust (0–255)

            for y in range(height):
                for x in range(width):
                    r, g, b = pixels[x, y]
                    gray = (r + g + b) // 3
                    
                    # Keep only pure black
                    if gray < threshold:
                        pixels[x, y] = (0, 0, 0)   # black
                    else:
                        pixels[x, y] = (255, 255, 255)  # white

            # Save result
            output_file = OUTPUT_DIR / f"{img_path.stem}_bw.png"
            img.save(output_file)

            print("Done. Saved to:", output_file)

        except Exception as e:
            print(f"  Error processing {img_path.name}: {e}")

    print("\nAll images processed successfully.")
    sys.exit(0)
    
if __name__ == "__main__":
    main()
