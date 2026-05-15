#!/usr/bin/env python3
"""
Moodle XML Generator for Multiple Choice Questions
Compatible with Moodle 4.0+
"""

import os
import xml.etree.ElementTree as ET
from xml.dom import minidom
import zipfile

# Configuration - UPDATE THESE PATHS
BASE_PATH = "/home/dkvlko/Dheeraj-Cloud-Drives/DheerajOnHP/BLOBS/Krish_Maths4/IMG_QS/SETA_1"
QTEXT_PATH = os.path.join(BASE_PATH, "qtext/img2txt")
QIMAGE_PATH = os.path.join(BASE_PATH, "qimage")
QOPT_A_PATH = os.path.join(BASE_PATH, "qopta")
QOPT_B_PATH = os.path.join(BASE_PATH, "qoptb")
QOPT_C_PATH = os.path.join(BASE_PATH, "qoptc")
QOPT_D_PATH = os.path.join(BASE_PATH, "qoptd")
QRIGHT_OPT_PATH = os.path.join(BASE_PATH, "qrtopt")

QXML_PATH = os.path.join(BASE_PATH, "qxml")
# Output files
OUTPUT_XML =os.path.join(QXML_PATH, "moodle_questions.xml")
OUTPUT_ZIP = os.path.join(QXML_PATH,"moodle_questions_bank.zip")

def get_question_ids():
    """Get all question IDs from the qtext folder"""
    question_ids = []
    for file in os.listdir(QTEXT_PATH):
        if file.endswith('-qtext.txt'):
            # Extract first 3 digits
            q_id = file[:3]
            if q_id.isdigit():
                question_ids.append(q_id)
    return sorted(question_ids)

def read_text_file(file_path):
    """Read text file content"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return ""

def is_image_file(file_path):
    """Check if file is an image"""
    return file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.svg'))

def format_for_moodle(text):
    """Format text for Moodle XML"""
    if not text:
        return ""
    # Escape XML special characters
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    text = text.replace('"', '&quot;')
    text = text.replace("'", '&apos;')
    return text

def get_question_text(q_id):
    """Get question text"""
    qtext_file = os.path.join(QTEXT_PATH, f"{q_id}-qtext.txt")
    if os.path.exists(qtext_file):
        return read_text_file(qtext_file)
    return ""

def get_question_image(q_id):
    """Get associated image for question if exists"""
    for ext in ['.png', '.jpg', '.jpeg', '.gif']:
        img_file = os.path.join(QIMAGE_PATH, f"{q_id}-qimage{ext}")
        if os.path.exists(img_file):
            return img_file
    return None

def get_option(q_id, option_letter):
    """Get option content (text or image)"""
    opt_folder = {
        'A': QOPT_A_PATH,
        'B': QOPT_B_PATH,
        'C': QOPT_C_PATH,
        'D': QOPT_D_PATH
    }[option_letter]
    
    # Check for text file first
    txt_file = os.path.join(opt_folder, f"{q_id}-qopt{option_letter.lower()}.txt")
    if os.path.exists(txt_file):
        return ('text', read_text_file(txt_file))
    
    # Check for image files
    for ext in ['.png', '.jpg', '.jpeg', '.gif']:
        img_file = os.path.join(opt_folder, f"{q_id}-qopt{option_letter.lower()}{ext}")
        if os.path.exists(img_file):
            return ('image', img_file)
    
    return ('text', "")

def get_correct_answer(q_id):
    """Get correct answer (A, B, C, or D)"""
    right_file = os.path.join(QRIGHT_OPT_PATH, f"{q_id}-qrtopt.txt")
    if os.path.exists(right_file):
        answer = read_text_file(right_file).strip().upper()
        if answer in ['A', 'B', 'C', 'D']:
            return answer
    return "A"  # Default fallback

def create_moodle_xml(questions_data):
    """Create Moodle XML structure"""
    
    # Create root element
    quiz = ET.Element('quiz')
    
    for q_data in questions_data:
        # Create question element
        question = ET.SubElement(quiz, 'question', type='multichoice')
        
        # Add name
        name = ET.SubElement(question, 'name')
        name_text = ET.SubElement(name, 'text')
        name_text.text = q_data['name']
        
        # Add question text (with possible image)
        questiontext = ET.SubElement(question, 'questiontext', format='html')
        text_elem = ET.SubElement(questiontext, 'text')
        
        # Build question HTML content
        question_html = ""
        
        # Add question image if exists
        if q_data.get('image'):
            # Get relative path or base64 encode the image
            question_html += f'<img src="{q_data["image"]}" alt="Question image" /><br/>'
        
        # Add question text
        question_html += format_for_moodle(q_data['question_text'])
        text_elem.text = question_html
        
        # Add general feedback (optional)
        generalfeedback = ET.SubElement(question, 'generalfeedback', format='html')
        gf_text = ET.SubElement(generalfeedback, 'text')
        gf_text.text = ""
        
        # Add default grade
        defaultgrade = ET.SubElement(question, 'defaultgrade')
        defaultgrade.text = "1"
        
        # Add penalty
        penalty = ET.SubElement(question, 'penalty')
        penalty.text = "0.3333333"
        
        # Add hidden (0 = not hidden)
        hidden = ET.SubElement(question, 'hidden')
        hidden.text = "0"
        
        # Add single answer (true = radio buttons)
        single = ET.SubElement(question, 'single')
        single.text = "true"
        
        # Add shuffle answers
        shuffleanswers = ET.SubElement(question, 'shuffleanswers')
        shuffleanswers.text = "true"
        
        # Add answernumbering
        answernumbering = ET.SubElement(question, 'answernumbering')
        answernumbering.text = "abc"
        
        # Add correct feedback
        correctfeedback = ET.SubElement(question, 'correctfeedback', format='html')
        cf_text = ET.SubElement(correctfeedback, 'text')
        cf_text.text = "Your answer is correct."
        
        # Add partially correct feedback
        partiallycorrectfeedback = ET.SubElement(question, 'partiallycorrectfeedback', format='html')
        pcf_text = ET.SubElement(partiallycorrectfeedback, 'text')
        pcf_text.text = "Your answer is partially correct."
        
        # Add incorrect feedback
        incorrectfeedback = ET.SubElement(question, 'incorrectfeedback', format='html')
        icf_text = ET.SubElement(incorrectfeedback, 'text')
        icf_text.text = "Your answer is incorrect."
        
        # Add options
        for letter in ['A', 'B', 'C', 'D']:
            answer = ET.SubElement(question, 'answer', fraction='100' if letter == q_data['correct_answer'] else '0', format='html')
            answer_text = ET.SubElement(answer, 'text')
            
            # Format option content
            if q_data['options'][letter]['type'] == 'text':
                option_content = format_for_moodle(q_data['options'][letter]['content'])
            else:  # image
                option_content = f'<img src="{q_data["options"][letter]["content"]}" alt="Option {letter}" />'
            
            answer_text.text = option_content
            
            # Add feedback for this answer
            feedback = ET.SubElement(answer, 'feedback', format='html')
            fb_text = ET.SubElement(feedback, 'text')
            fb_text.text = ""
    
    return quiz

def process_questions():
    """Process all questions from the folders"""
    question_ids = get_question_ids()
    questions_data = []
    
    print(f"Found {len(question_ids)} questions")
    
    for q_id in question_ids:
        print(f"Processing question {q_id}...")
        
        q_data = {
            'id': q_id,
            'name': f"{q_id}-qtext",  # Filename without extension
            'question_text': get_question_text(q_id),
            'image': get_question_image(q_id),
            'options': {},
            'correct_answer': get_correct_answer(q_id)
        }
        
        # Get options
        for letter in ['A', 'B', 'C', 'D']:
            opt_type, opt_content = get_option(q_id, letter)
            q_data['options'][letter] = {
                'type': opt_type,
                'content': opt_content
            }
        
        # Validate
        if not q_data['question_text']:
            print(f"  Warning: No question text found for {q_id}")
        
        if not any(q_data['options'][l]['content'] for l in 'ABCD'):
            print(f"  Warning: No options found for {q_id}")
        
        questions_data.append(q_data)
    
    return questions_data

def prettify_xml(elem):
    """Return pretty-printed XML string"""
    rough_string = ET.tostring(elem, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")

def create_zip_with_images(xml_file, questions_data, zip_name):
    """Create ZIP file with XML and all images"""
    with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # Add XML file
        zipf.write(xml_file, os.path.basename(xml_file))
        
        # Add all images
        added_images = set()
        
        for q_data in questions_data:
            # Add question image
            if q_data.get('image') and q_data['image'] not in added_images:
                if os.path.exists(q_data['image']):
                    arcname = f"images/{os.path.basename(q_data['image'])}"
                    zipf.write(q_data['image'], arcname)
                    added_images.add(q_data['image'])
                    # Update image path in XML? We'll handle via relative paths
            
            # Add option images
            for letter in 'ABCD':
                if q_data['options'][letter]['type'] == 'image':
                    img_path = q_data['options'][letter]['content']
                    if img_path and img_path not in added_images:
                        if os.path.exists(img_path):
                            arcname = f"images/{os.path.basename(img_path)}"
                            zipf.write(img_path, arcname)
                            added_images.add(img_path)
        
        print(f"Added {len(added_images)} images to ZIP")

def main():
    """Main function"""
    print("=" * 60)
    print("Moodle XML Question Bank Generator")
    print("=" * 60)
    print(f"Base path: {BASE_PATH}")
    print()
    
    # Check if paths exist
    if not os.path.exists(QTEXT_PATH):
        print(f"Error: Question text path not found: {QTEXT_PATH}")
        return
    
    # Process questions
    questions_data = process_questions()
    
    if not questions_data:
        print("No questions found to process!")
        return
    
    # Create XML
    print("\nGenerating Moodle XML...")
    xml_root = create_moodle_xml(questions_data)
    
    # Write XML file
    with open(OUTPUT_XML, 'w', encoding='utf-8') as f:
        xml_string = prettify_xml(xml_root)
        f.write(xml_string)
    
    print(f"XML file created: {OUTPUT_XML}")
    
    # Create ZIP file
    print("\nCreating ZIP archive...")
    create_zip_with_images(OUTPUT_XML, questions_data, OUTPUT_ZIP)
    
    print(f"ZIP file created: {OUTPUT_ZIP}")
    print(f"Total questions processed: {len(questions_data)}")
    print("\n" + "=" * 60)
    print("Generation complete!")
    print("=" * 60)

if __name__ == "__main__":
    main()
