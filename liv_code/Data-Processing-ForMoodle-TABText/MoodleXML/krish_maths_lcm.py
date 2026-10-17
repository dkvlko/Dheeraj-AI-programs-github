import random
import math
from pathlib import Path

def is_prime(n):
    if n <= 1:
        return False
    # Only need to check up to the square root of n
    for i in range(2, int(n**0.5) + 1):
        if n % i == 0:
            return False
    return True

def generate_lcm_quiz_xml(filename: str = "moodle_lcm_quiz.xml", total_questions: int = 20) -> None:
    # Initialize the standard Moodle XML quiz structure
    xml_content = '<?xml version="1.0" encoding="UTF-8"?>\n<quiz>\n'
    
    generated_count = 0
    
    while generated_count < total_questions:
        # 1. Generate two random positive integers between 11 and 250
        isa_prime=True
        isb_prime=True
        while isa_prime or isb_prime  :
            a = random.randint(11, 250)
            b = random.randint(11, 250)
            isa_prime=is_prime(a)
            isb_prime=is_prime(b)
        

        # 2. Calculate the Least Common Multiple (LCM)
        # Using math.gcd() to derive LCM safely: LCM(a, b) = (a * b) / GCD(a, b)
        hcf_gcd = math.gcd(a, b)
        lcm = (a * b) // hcf_gcd
        
        # 3. Guard rail: Ensure LCM is strictly greater than 2
        if lcm <= 2:
            continue  # Reject the pair and roll fresh numbers
            
        generated_count += 1
        
        # 4. Append individual Cloze question node with embedded auto-verification box
        xml_content += f"""  <question type="cloze">
    <name>
      <text>Dynamic LCM Question {generated_count:02d}</text>
    </name>
    <questiontext format="html">
      <text><![CDATA[
        <p>Find the Least Common Multiple (LCM) of the following two positive numbers:</p>
        <p style="font-size: 1.2em; font-weight: bold; color: #1a56db;">\\({a}\\) and \\({b}\\)</p>
        <p><strong>LCM = </strong> {{1:NUMERICAL:={lcm}:0}}</p>
      ]]></text>
    </questiontext>
    <generalfeedback format="html">
      <text><![CDATA[<p>The LCM of {a} and {b} is {lcm}.</p>]]></text>
    </generalfeedback>
    <defaultgrade>1.0000000</defaultgrade>
    <penalty>0.3333333</penalty>
    <hidden>0</hidden>
    <idnumber></idnumber>
  </question>\n"""

    xml_content += "</quiz>"
    file_str = f"/home/dkvlko/Dheeraj-Cloud-Drives/DheerajOnHP/BLOBS/Krish_Maths4/xmls/{filename}"
    filename = Path(file_str)
    # Write the compiled tree structure out to file using strict UTF-8 formatting
    with open(filename, "w", encoding="utf-8") as xml_file:
        xml_file.write(xml_content)
        
    print(f"Success! Generated '{filename}' containing {total_questions} dynamic LCM questions.")

if __name__ == "__main__":
    # Execute script layer
    generate_lcm_quiz_xml()
