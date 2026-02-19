def process(data):

    BLANK_TOKEN = "$Blankspace$"
    START_TOKEN = "{{c1::"
    END_TOKEN = "}}"

    for row in data:

        answers_in_row = []   # collect answers for this row

        for col_index in range(len(row)):

            cell_value = row[col_index]

            if isinstance(cell_value, str) and START_TOKEN in cell_value:

                start_pos = cell_value.find(START_TOKEN)

                if start_pos != -1:
                    start_pos += len(START_TOKEN)

                    end_pos = cell_value.find(END_TOKEN, start_pos)

                    if end_pos != -1:
                        # Extract answer
                        answer = cell_value[start_pos:end_pos]
                        answers_in_row.append(answer)

                        # Replace cloze with blank token
                        new_value = (
                            cell_value[:start_pos - len(START_TOKEN)]
                            + BLANK_TOKEN
                            + cell_value[end_pos + len(END_TOKEN):]
                        )

                        row[col_index] = new_value

        # Append extracted answers as new columns
        for ans in answers_in_row:
            row.append(ans)

    return data

def process_4gift(data):

    for row in data:
        if len(row) >= 3:
            row[2] = row[2].upper()

    return data


def process_4gift(data):

    for row in data:
        if len(row) >= 3:
            row[2] = row[2].upper()

    return data
