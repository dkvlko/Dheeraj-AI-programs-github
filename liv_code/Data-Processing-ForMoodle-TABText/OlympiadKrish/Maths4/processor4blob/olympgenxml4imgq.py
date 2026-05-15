import os
import base64
import glob
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom

# Path Configuration
BASE_PATH = "/home/dkvlko/Dheeraj-Cloud-Drives/DheerajOnHP/BLOBS/Krish_Maths4/IMG_QS/SETA_1"
PATHS = {
    "qtext": os.path.join(BASE_PATH, "qtext/img2txt"),
    "qimage": os.path.join(BASE_PATH, "qimage"),
    "qopta": os.path.join(BASE_PATH, "qopta"),
    "qoptb": os.path.join(BASE_PATH, "qoptb"),
    "qoptc": os.path.join(BASE_PATH, "qoptc"),
    "qoptd": os.path.join(BASE_PATH, "qoptd"),
    "qrtopt": os.path.join(BASE_PATH, "qrtopt"),
    "qxml": os.path.join(BASE_PATH, "qxml")
}

def get_base64_img(file_path):
    if not os.path.exists(file_path):
        return None
    with open(file_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode('utf-8')

def create_moodle_xml():
    os.makedirs(PATHS["qxml"], exist_ok=True)
    quiz = Element('quiz')
    
    q_files = glob.glob(os.path.join(PATHS["qtext"], "*.txt"))
    
    for q_file_path in sorted(q_files):
        filename = os.path.basename(q_file_path)
        q_id = filename[:3]
        
        question = SubElement(quiz, 'question', {'type': 'multichoice'})
        name = SubElement(question, 'name')
        SubElement(name, 'text').text = os.path.splitext(filename)[0]
        
        # 1. Question Text Processing
        with open(q_file_path, 'r', encoding="utf-8") as f:
            q_text_content = f.read().strip()
            
        q_text_node = SubElement(question, 'questiontext', {'format': 'html'})
        
        img_match = glob.glob(os.path.join(PATHS["qimage"], f"{q_id}*"))
        img_html = ""
        if img_match:
            ext = os.path.splitext(img_match[0])[1][1:]
            b64 = get_base64_img(img_match[0])
            img_html = f'<p><img src="data:image/{ext};base64,{b64}" /></p>'
        
        # Wrapping in CDATA string
        SubElement(q_text_node, 'text').text = f"<![CDATA[<p>{q_text_content}</p>{img_html}]]>"

        # 2. Get Correct Answer
        ans_file = os.path.join(PATHS["qrtopt"], f"{q_id}.txt")
        correct_letter = "A"
        if os.path.exists(ans_file):
            with open(ans_file, 'r') as f:
                correct_letter = f.read().strip().upper()

        # 3. Options Processing
        for letter in ['A', 'B', 'C', 'D']:
            folder = PATHS[f"qopt{letter.lower()}"]
            opt_match = glob.glob(os.path.join(folder, f"{q_id}*"))
            
            fraction = "100" if letter == correct_letter else "0"
            answer = SubElement(question, 'answer', {'fraction': fraction, 'format': 'html'})
            ans_text_node = SubElement(answer, 'text')
            
            if opt_match:
                opt_path = opt_match[0]
                if opt_path.lower().endswith(('.png', '.jpg', '.jpeg')):
                    ext = os.path.splitext(opt_path)[1][1:]
                    b64 = get_base64_img(opt_path)
                    content = f'<img src="data:image/{ext};base64,{b64}" />'
                else:
                    with open(opt_path, 'r', encoding="utf-8") as f:
                        content = f.read().strip()
                
                # Critical: Wrap content in CDATA
                ans_text_node.text = f"<![CDATA[{content}]]>"
            else:
                ans_text_node.text = f"Option {letter} Missing"

        SubElement(question, 'single').text = "true"
        SubElement(question, 'shuffleanswers').text = "1"
        SubElement(question, 'answernumbering').text = "abc"

    # Final XML Formatting and Clean-up
    xml_output = tostring(quiz, encoding='utf-8')
    xml_str = minidom.parseString(xml_output).toprettyxml(indent="   ")
    
    # This prevents Python from escaping the CDATA tags
    xml_str = xml_str.replace("&lt;![CDATA[", "<![CDATA[").replace("]]&gt;", "]]>")
    
    output_file = os.path.join(PATHS["qxml"], "moodle_questions.xml")
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(xml_str)
    
    print(f"Success! XML generated at: {output_file}")

if __name__ == "__main__":
    create_moodle_xml()
