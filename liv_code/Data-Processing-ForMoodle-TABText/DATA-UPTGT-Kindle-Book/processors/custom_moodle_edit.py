import re

file_path = "/home/dkvlko/Dheeraj-AI-programs-github/liv_code/Data-Processing-ForMoodle-TABText/DATA-UPTGT-Kindle-Book/COMBINED_TEXT_KINDLE/UPTGT-Eng-Lit_Combined_Text_final_check.txt"

with open(file_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

i = 0

while i < len(lines):

    if "#FIXIT" in lines[i]:

        question_line = lines[i+1].strip()

        print("\nProblematic MCQ:\n")
        print(question_line)
        print()

        # extract options
        match = re.search(r"\{(.*)\}", question_line)

        if not match:
            print("Could not parse options.")
            i += 1
            continue

        option_text = match.group(1)

        # split options but keep prefix
        options = re.split(r'(?=[=~])', option_text)

        # collect ~ options
        tilde_options = []
        for idx, opt in enumerate(options):
            if opt.startswith("~"):
                tilde_options.append((idx, opt))

        print("Options you can delete:\n")

        for num, (idx, opt) in enumerate(tilde_options, start=1):
            print(f"{num}: {opt}")

        choice = int(input("\nEnter option number to delete: "))

        delete_index = tilde_options[choice-1][0]

        # remove selected option
        del options[delete_index]

        new_option_text = "".join(options)

        new_line = re.sub(r"\{.*\}", "{" + new_option_text + "}", question_line)

        # replace question line
        lines[i+1] = new_line + "\n"

        # remove FIXIT line
        del lines[i]

        print("\nUpdated MCQ:")
        print(new_line)
        print("-"*60)

        continue

    i += 1


with open(file_path, "w", encoding="utf-8") as f:
    f.writelines(lines)

print("\nFinished fixing file.")