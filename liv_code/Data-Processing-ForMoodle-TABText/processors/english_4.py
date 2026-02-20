# english_2.py

import sys
import os
import re

# Get parent directory of this script
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Add to sys.path
sys.path.insert(0, parent_dir)

# Now import file_io



def process_mcq_backup(data):

    if not data:
        return data

    header = data[0]  # First row is header
    # Track which columns already renamed
    iMcq=0
    
    # Process each data row (skip header)
    for row_index in range(1, len(data)):
        row = data[row_index]

        extracted_values = []

        # Iterate through original columns only
        original_length = len(row)

        for col_index in range(original_length):
            cell_value = row[col_index]

            # ---- Detect first occurrence for this column ----
            if " / " in cell_value and iMcq == 0:
                iMcq=col_index
                

            while " / " in cell_value:
                left_part, right_part = cell_value.split(" / ", 1)

                extracted_values.append(left_part)

                cell_value = right_part

            row[col_index] = cell_value

        # Append extracted values to row
        row.extend(extracted_values)
    
    max_cols = max(len(row) for row in data)

    #data = update_column_header(data,iMcq, max_cols, "MCQ")
    return data


def process_mcq(data):

    processed_data = []

    for row in data:

        new_row = []

        for cell in row:

            if " / " in cell:
                # Split and clean
                parts = [part.strip() for part in cell.split(" / ") if part.strip()]

                # Append $MCQ$ and extend row
                for part in parts:
                    new_row.append(part + "$MCQ$")
            else:
                new_row.append(cell)

        processed_data.append(new_row)

    return processed_data


#Handle single cloze replacement

def process_cloze_backup(data):

    START_TOKEN = "{{c1::"
    END_TOKEN = "}}"
    BLANK_TOKEN = "$Blankspace$"

    if not data:
        return data

    header = data[0]

    # Track which answer headers are already added
    existing_headers = set(header)

    # ---- Process data rows (skip header) ----
    for row in data[1:]:

        answers = []

        for col_index, cell in enumerate(row):

            if START_TOKEN in cell:

                while START_TOKEN in cell:
                    start = cell.find(START_TOKEN)
                    end = cell.find(END_TOKEN, start)

                    if end == -1:
                        break  # malformed cloze

                    # Extract answer
                    answer = cell[start + len(START_TOKEN):end]
                    answers.append(answer)

                    # Replace cloze with blank token
                    cell = (
                        cell[:start]
                        + BLANK_TOKEN
                        + cell[end + len(END_TOKEN):]
                    )

                row[col_index] = cell

        # Append extracted answers to row
        if answers:
            row.extend(answers)

            # Add headers if not already present
            for i in range(len(answers)):
                header_name = f"{len(header) + i}Ans"
                if header_name not in existing_headers:
                    header.append(header_name)
                    existing_headers.add(header_name)

    return data

def process_cloze(data):
    START_TOKEN = "{{c1::"
    END_TOKEN = "}}"
    BLANK_TOKEN = "$Blankspace$"
    FIB_PREFIX = "$FIB$"

    for row in data:
        fib_list = []

        for col_idx, cell in enumerate(row):
            if not isinstance(cell, str):
                continue

            while START_TOKEN in cell:
                start = cell.find(START_TOKEN)
                end = cell.find(END_TOKEN, start)

                # Safety check: malformed cloze
                if end == -1:
                    break

                # Extract answer text
                answer = cell[start + len(START_TOKEN):end]
                fib_list.append(FIB_PREFIX + answer)

                # Replace cloze with blankspace
                cell = (
                    cell[:start]
                    + BLANK_TOKEN
                    + cell[end + len(END_TOKEN):]
                )

            # Update the modified cell back into row
            row[col_idx] = cell

        # ✅ KEY CHANGE HERE
        if fib_list:
            row.extend(fib_list)   # instead of append()

    return data


def process_4gift_premitive(data):

    for row in data:
        if len(row) >= 3:
            row[2] = row[2].upper()

    return data

def process_4gift_backup(data):

    gift_questions = []

    for row in data:

        #if len(row) < 4:
        #    continue

        q1 = row[1].strip()
        q2 = row[2].strip()
        ans = row[3].strip()

        #print(f"Ans: {ans}")

        # Replace blank token
        if "$Blankspace$" in q2:
            q2 = q2.replace(
                "$Blankspace$",
                f"{{={ans}}}"
            )

        # Merge text
        full_question = q1 + "\n" + q2

        # Create GIFT block
        gift_block = f"::Question::\n{full_question}\n"

        gift_questions.append(gift_block)

    return gift_questions




def process_4gift_notgood(data):
    """
    Convert TAB-delimited data (list of rows) into GIFT format strings.

    Rules implemented as per specification:
    - Ignore first column.
    - Build question text until a $ token is found.
    - Handle $Blankspace$, $MCQ$, $FIB$.
    - Re-scan same cell after token removal.
    """

    gift_questions = []

    for row_idx, row in enumerate(data):

        if len(row) <= 1:
            continue  # nothing usable

        question_parts = []
        options = []
        answers = []
        blanks_count = 0

        col = 1  # start from second column

        # -----------------------------
        # STEP 1 — BUILD QUESTION TEXT
        # -----------------------------
        token_found = False

        while col < len(row):
            cell = str(row[col]).strip()

            if not cell:
                col += 1
                continue

            if "$" not in cell:
                question_parts.append(cell)
                col += 1
                continue

            # Token exists → process cell
            token_found = True

            # Keep rescanning same cell
            while "$" in cell:

                # ---- Blankspace ----
                if "$Blankspace$" in cell:
                    blanks_count += 1
                    cell = cell.replace("$Blankspace$", "_____")

                # ---- MCQ option ----
                elif "$MCQ$" in cell:
                    text = cell.replace("$MCQ$", "").strip()
                    if text:
                        options.append(text)
                    cell = ""

                # ---- FIB answer ----
                elif "$FIB$" in cell:
                    text = cell.replace("$FIB$", "").strip()
                    if text:
                        answers.append(text)
                    cell = ""

                else:
                    # Unknown $ token → remove $
                    cell = cell.replace("$", "")

            # Remaining text becomes part of question
            if cell.strip():
                question_parts.append(cell.strip())

            col += 1
            break  # question text phase ends after first token

        # Continue scanning remaining columns for options/answers
        while col < len(row):
            cell = str(row[col]).strip()

            if not cell:
                col += 1
                continue

            while "$" in cell:

                if "$Blankspace$" in cell:
                    blanks_count += 1
                    cell = cell.replace("$Blankspace$", "_____")

                elif "$MCQ$" in cell:
                    text = cell.replace("$MCQ$", "").strip()
                    if text:
                        options.append(text)
                    cell = ""

                elif "$FIB$" in cell:
                    text = cell.replace("$FIB$", "").strip()
                    if text:
                        answers.append(text)
                    cell = ""

                else:
                    cell = cell.replace("$", "")

            col += 1

        # -----------------------------
        # STEP 2 — BUILD QUESTION TEXT
        # -----------------------------
        question_text = "\n".join(question_parts).strip()

        if not question_text:
            continue

        # -----------------------------
        # STEP 3 — BUILD GIFT
        # -----------------------------
        gift = ""

        # Fill in the blanks
        if blanks_count > 0:
            if answers:
                answer_block = " = " + " = ".join(answers)
            else:
                answer_block = ""

            gift = f"{question_text} {{ {answer_block} }}"

        # Multiple choice
        elif options:
            opt_block = ""

            for opt in options:
                if opt in answers:
                    opt_block += f"={opt}\n"
                else:
                    opt_block += f"~{opt}\n"

            gift = f"{question_text} {{\n{opt_block}}}"

        else:
            # Essay / description fallback
            gift = f"{question_text} {{}}"

        gift_questions.append(gift)

    return gift_questions

def process_4gift(data):
    gift_output = []

    for row_index, row in enumerate(data):

        if not row or len(row) < 2:
            continue  # skip invalid rows

        # -----------------------------
        # STEP 1 — Build QuestionMoodle
        # -----------------------------
        question_parts = []
        blank_col_index = None

        for col_index in range(1, len(row)):  # ignore first column
            cell = str(row[col_index]).strip()

            if "$" not in cell:
                question_parts.append(cell)
            else:
                question_parts.append(cell)
                blank_col_index = col_index
                break

        if blank_col_index is None:
            continue  # no blankspace found

        QuestionMoodle = "\n".join(question_parts)

        print(QuestionMoodle)
        # -----------------------------
        # STEP 2 — Collect MCQ
        # -----------------------------
        MCQ = []
        last_mcq_col = None

        for col_index in range(blank_col_index + 1, len(row)):
            cell = str(row[col_index]).strip()

            if not cell:
                break

            if "$FIB$" in cell:
                break

            if "$MCQ$" in cell:
                cell= cell.replace("$MCQ$", "").strip()
                MCQ.append(cell)
                last_mcq_col = col_index

        # -----------------------------
        # STEP 3 — Collect FIB
        # -----------------------------
        FIB = []

        if last_mcq_col is not None:
            for col_index in range(last_mcq_col + 1, len(row)):
                cell = str(row[col_index]).strip()

                if not cell:
                    break

                if "$FIB$" in cell:
                    cell = cell.replace("$FIB$", "").strip()
                    FIB.append(cell)

        # -----------------------------
        # STEP 4 — Print debug
        # -----------------------------
        #print("\nRow:", row_index)
        #print("QuestionMoodle:\n", QuestionMoodle)
        #print("MCQ:", MCQ)
        #print("FIB:", FIB)

        if not FIB:
            continue  # cannot build cloze without answer

        # -----------------------------
        # STEP 5 — Build Cloze
        # -----------------------------
        cloze = "{="

        # Add answer first
        cloze += FIB[0]

        # Add MCQ distractors
        for option in MCQ:
            if option != FIB[0]:
                cloze += " ~" + option

        cloze += "}"

        print("Raw Cloze:", cloze)


        # Replace Blankspace
        QuestionMoodle = QuestionMoodle.replace("$Blankspace$", cloze)

        # -----------------------------
        # Convert to GIFT entry
        # -----------------------------
        gift_question = f"::{row_index}:: {QuestionMoodle}\n"

        gift_output.append(gift_question)

    return gift_output
