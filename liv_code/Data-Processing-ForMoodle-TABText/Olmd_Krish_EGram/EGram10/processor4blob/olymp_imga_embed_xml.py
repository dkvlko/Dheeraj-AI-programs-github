#!/usr/bin/env python3
"""
Moodle XML Generator for Multiple Choice Questions with embedded images
Compatible with Moodle 4.0+
"""

import os
import xml.etree.ElementTree as ET
from xml.dom import minidom
import base64

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
OUTPUT_XML =os.path.join(QXML_PATH, "moodle_questions_with_images.xml")
# Output file

def get_question_ids():
    """Get all question IDs from the qtext folder"""
    question_ids = []
    for file in os.listdir(QTEXT_PATH):
        if file.endswith('-qtext.txt'):
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

def image_to_base64(image_path):
    """Convert image file to base64 encoded string"""
    try:
        with open(image_path, 'rb') as img_file:
            img_data = img_file.read()
            img_base64 = base64.b64encode(img_data).decode('utf-8')
            
            # Determine MIME type
            if image_path.lower().endswith('.png'):
                mime_type = 'image/png'
            elif image_path.lower().endswith('.jpg') or image_path.lower().endswith('.jpeg'):
                mime_type = 'image/jpeg'
            elif image_path.lower().endswith('.gif'):
                mime_type = 'image/gif'
            else:
                mime_type = 'image/png'
            
            return f'<img src="data:{mime_type};base64,{img_base64}" alt="Image" />'
    except Exception as e:
        print(f"Error converting image to base64: {e}")
        return ""

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

def get_question_image_html(q_id):
    """Get associated image for question as HTML"""
    for ext in ['.png', '.jpg', '.jpeg', '.gif']:
        img_file = os.path.join(QIMAGE_PATH, f"{q_id}-qimage{ext}")
        if os.path.exists(img_file):
            return image_to_base64(img_file)
    return ""

def get_option_html(q_id, option_letter):
    """Get option content as HTML (text or embedded image)"""
    opt_folder = {
        'A': QOPT_A_PATH,
        'B': QOPT_B_PATH,
        'C': QOPT_C_PATH,
        'D': QOPT_D_PATH
    }[option_letter]
    
    # Check for text file first
    txt_file = os.path.join(opt_folder, f"{q_id}-qopt{option_letter.lower()}.txt")
    if os.path.exists(txt_file):
        return format_for_moodle(read_text_file(txt_file))
    
    # Check for image files
    for ext in ['.png', '.jpg', '.jpeg', '.gif']:
        img_file = os.path.join(opt_folder, f"{q_id}-qopt{option_letter.lower()}{ext}")
        if os.path.exists(img_file):
            return image_to_base64(img_file)
    
    return ""

def get_correct_answer(q_id):
    """Get correct answer (A, B, C, or D)"""
    right_file = os.path.join(QRIGHT_OPT_PATH, f"{q_id}-qrtopt.txt")
    if os.path.exists(right_file):
        answer = read_text_file(right_file).strip().upper()
        if answer in ['A', 'B', 'C', 'D']:
            return answer
    return "A"

def create_moodle_xml(questions_data):
    """Create Moodle XML structure with embedded images"""
    
    quiz = ET.Element('quiz')
    
    for q_data in questions_data:
        question = ET.SubElement(quiz, 'question', type='multichoice')
        
        # Add name
        name = ET.SubElement(question, 'name')
        name_text = ET.SubElement(name, 'text')
        name_text.text = q_data['name']
        
        # Add question text with embedded images
        questiontext = ET.SubElement(question, 'questiontext', format='html')
        text_elem = ET.SubElement(questiontext, 'text')
        
        # Build question HTML content
        question_html = ""
        
        # Add question image if exists
        if q_data.get('image_html'):
            question_html += q_data['image_html'] + "<br/>"
        
        # Add question text
        question_html += format_for_moodle(q_data['question_text'])
        text_elem.text = question_html
        
        # Add general feedback
        generalfeedback = ET.SubElement(question, 'generalfeedback', format='html')
        gf_text = ET.SubElement(generalfeedback, 'text')
        gf_text.text = ""
        
        # Add default grade
        defaultgrade = ET.SubElement(question, 'defaultgrade')
        defaultgrade.text = "1"
        
        # Add penalty
        penalty = ET.SubElement(question, 'penalty')
        penalty.text = "0.3333333"
        
        # Add hidden
        hidden = ET.SubElement(question, 'hidden')
        hidden.text = "0"
        
        # Add single answer
        single = ET.SubElement(question, 'single')
        single.text = "true"
        
        # Add shuffle answers
        shuffleanswers = ET.SubElement(question, 'shuffleanswers')
        shuffleanswers.text = "true"
        
        # Add answernumbering
        answernumbering = ET.SubElement(question, 'answernumbering')
        answernumbering.text = "abc"
        
        # Add feedback
        correctfeedback = ET.SubElement(question, 'correctfeedback', format='html')
        cf_text = ET.SubElement(correctfeedback, 'text')
        cf_text.text = "Your answer is correct."
        
        partiallycorrectfeedback = ET.SubElement(question, 'partiallycorrectfeedback', format='html')
        pcf_text = ET.SubElement(partiallycorrectfeedback, 'text')
        pcf_text.text = "Your answer is partially correct."
        
        incorrectfeedback = ET.SubElement(question, 'incorrectfeedback', format='html')
        icf_text = ET.SubElement(incorrectfeedback, 'text')
        icf_text.text = "Your answer is incorrect."
        
        # Add options
        for option_letter in ['A', 'B', 'C', 'D']:
            answer = ET.SubElement(question, 'answer', 
                                 fraction='100' if option_letter == q_data['correct_answer'] else '0', 
                                 format='html')
            answer_text = ET.SubElement(answer, 'text')
            answer_text.text = q_data['options'][option_letter]
            
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
            'name': f"{q_id}-qtext",
            'question_text': get_question_text(q_id),
            'image_html': get_question_image_html(q_id),
            'options': {},
            'correct_answer': get_correct_answer(q_id)
        }
        
        # Get options as HTML
        for option_letter in ['A', 'B', 'C', 'D']:
            q_data['options'][option_letter] = get_option_html(q_id, option_letter)
        #================debug prints===============
        # Simplified but informative printing
#        print(f"\n{'='*50}")
#        print(f"Q{q_id}: {q_data['name']}")
#        print(f"{'='*50}")
#        print(f"Text: {q_data['question_text'][:100]}..." if len(q_data['question_text']) > 100 else f"Text: {q_data['question_text']}")
#        print(f"Image: {'✓' if q_data['image_html'] else '✗'}")
#        print(f"Answer: {q_data['correct_answer']}")
#        print(f"\nOptions:")
#        for opt in 'ABCD':
#            has_content = '✓' if q_data['options'][opt] else '✗'
#            opt_type = 'img' if q_data['options'][opt] and q_data['options'][opt].startswith('<img') else 'txt' if q_data['options'][opt] else '---'
#            print(f"  {opt}: [{has_content}] {opt_type}", end='')
#            if q_data['options'][opt] and opt == q_data['correct_answer']:
#                print(" ★ CORRECT", end='')
#            print()
#        print(f"{'='*50}\n")
#=================================
        # Validate
        if not q_data['question_text']:
            print(f"  Warning: No question text found for {q_id}")
        
        has_options = False
        for option_letter in ['A', 'B', 'C', 'D']:
            if q_data['options'][option_letter]:
                has_options = True
                break
        
        if not has_options:
            print(f"  Warning: No options found for {q_id}")
        
        questions_data.append(q_data)
    
    return questions_data

def prettify_xml(elem):
    """Return pretty-printed XML string"""
    rough_string = ET.tostring(elem, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")

def main():
    """Main function"""
    print("=" * 60)
    print("Moodle XML Question Bank Generator (with embedded images)")
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
    print("\nGenerating Moodle XML with embedded images...")
    xml_root = create_moodle_xml(questions_data)
    
    # Write XML file
    with open(OUTPUT_XML, 'w', encoding='utf-8') as f:
        xml_string = prettify_xml(xml_root)
        f.write(xml_string)
    
    file_size = os.path.getsize(OUTPUT_XML) / 1024  # KB
    print(f"XML file created: {OUTPUT_XML}")
    print(f"File size: {file_size:.2f} KB")
    print(f"Total questions processed: {len(questions_data)}")
    
    print("\n" + "=" * 60)
    print("Generation complete!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Log into Moodle as Administrator or Course Manager")
    print("2. Navigate to your course")
    print("3. Go to Question bank → Import")
    print("4. Select 'Moodle XML format'")
    print(f"5. Upload '{OUTPUT_XML}' (this is the ONLY file you need)")
    print("6. Click Import")
    print("\nNote: Images are embedded directly in the XML file,")
    print("so no separate image files are needed!")

if __name__ == "__main__":
    main()
