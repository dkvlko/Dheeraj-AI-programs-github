import re

def process_mcq_file(input_file, output_file):
    SNo = 0
    QuestionMoodle_list = []

    with open(input_file, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip() != ""]

    i = 0
    total_lines = len(lines)

    while i < total_lines:

        line = lines[i]

        # ---- Detect Question line (e.g., 1. What is ... ?) ----
        q_match = re.match(r'^\d+\.\s*(.*\?)$', line)

        if q_match:
            question = q_match.group(1)

            MCQ = []
            RANS = []

            i += 1

            # ---- Read options until "Answer:" is found ----
            while i < total_lines:

                opt_line = lines[i]

                # Match options like A. Apple
                opt_match = re.match(r'^([A-Za-z])\.\s*(.*)$', opt_line)

                if opt_match:
                    option_text = opt_match.group(2).strip()
                    MCQ.append(option_text)

                # Match Answer line
                ans_match = re.match(r'^Answer:\s*(.*)$', opt_line, re.IGNORECASE)

                if ans_match:
                    answer_text = ans_match.group(1).strip()
                    RANS.append(answer_text)
                    break

                i += 1

            # ---- Build Moodle GIFT string ----
            if RANS:
                QuestionMoodle = "::"
                QuestionMoodle += str(SNo)
                QuestionMoodle += ":: "
                QuestionMoodle += question
                QuestionMoodle += " {="

                # Correct answer
                QuestionMoodle += RANS[0]

                # Add incorrect options
                for opt in MCQ:
                    if opt.strip().lower() != RANS[0].strip().lower():
                        QuestionMoodle += " ~" + opt

                QuestionMoodle += "}\n\n"

                QuestionMoodle_list.append(QuestionMoodle)

                SNo += 1

        i += 1

    # ---- Write output ----
    with open(output_file, "w", encoding="utf-8") as f:
        f.writelines(QuestionMoodle_list)

    print(f"Processed {SNo} questions.")


def main():
    # ---- Usage ----
    input_file = "12000-Clues-6000-Words.txt"
    output_file = "12000-Clues-6000-Words.gift"

    process_mcq_file(input_file, output_file)


if __name__ == "__main__":
    main()
