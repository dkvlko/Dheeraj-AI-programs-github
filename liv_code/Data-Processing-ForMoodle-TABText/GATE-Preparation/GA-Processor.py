import base64
import csv
import os
from pathlib import Path
from xml.sax.saxutils import escape


# Initialize SCRIPT_DIR
SCRIPT_DIR = Path(__file__).resolve().parent

#print(f"Python folder : {SCRIPT_DIR}")

# Two level up
INPUT_DIR= SCRIPT_DIR.parent.parent


IMAGES_FOLDER = f"{INPUT_DIR}/BLOBS/GATE-2026-GA"

#print(f"Input folder : {INPUT_DIR}")
#print(f"Images folder : {IMAGES_FOLDER}")

CSV_FILE = "answers.csv"
OUTPUT_FILE = "moodle_questions.xml"


def encode_image_to_base64(filepath):
    with open(filepath, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def create_question_xml(qname, image_name, image_b64, answer):
    return f"""
  <question type="shortanswer">
    <name>
      <text>{escape(qname)}</text>
    </name>

    <questiontext format="html">
      <text><![CDATA[
        <p>Answer the question:</p>
        <img src="@@PLUGINFILE@@/{image_name}">
      ]]></text>

      <file name="{image_name}" path="/" encoding="base64">
        {image_b64}
      </file>
    </questiontext>

    <answer fraction="100">
      <text>{escape(answer)}</text>
    </answer>

    <answer fraction="0">
      <text>*</text>
    </answer>
  </question>
"""


def main():
    questions_xml = ""

    with open(CSV_FILE, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        #print(f"📊 Processing CSV: {CSV_FILE}")
        #print(f"Total questions found: {sum(1 for _ in reader)}")
        #csvfile.seek(0)  # Reset file pointer to the beginning after counting   
        
        for i, row in enumerate(reader, start=1):
            filename = row["filename"].strip()
            answer = row["answer"].strip()

            #print(f"Processing: {filename} with answer: {answer}")

            image_path = os.path.join(IMAGES_FOLDER, filename)

            print(f"Looking for image at: {image_path}")

            if not os.path.exists(image_path):
                print(f"⚠️ Missing image: {filename}")
                continue

            image_b64 = encode_image_to_base64(image_path)

            question_xml = create_question_xml(
                qname=f"Q{i}",
                image_name=filename,
                image_b64=image_b64,
                answer=answer
            )

            questions_xml += question_xml

    final_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<quiz>
{questions_xml}
</quiz>
"""

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(final_xml)

    print(f"✅ XML file generated: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()