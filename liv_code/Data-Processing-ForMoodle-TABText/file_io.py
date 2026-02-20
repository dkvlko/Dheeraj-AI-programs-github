import csv
from config import BASE_DIR, INPUT_PATTERN, INPUT_PATTERN_GIFT, OUTPUT_SUFFIX, OUTPUT_SUFFIX_GIFT
import re

def get_input_output_paths(file_number: int):
    """Create input & output file paths."""
    
    input_name = INPUT_PATTERN.format(num=file_number)
    output_name = input_name.replace(".csv", f"{OUTPUT_SUFFIX}.csv")

    input_path = BASE_DIR / "Data_EngGrmr" /input_name
    output_path = BASE_DIR / "Data_EngGrmr" / output_name

    input_name_gift = INPUT_PATTERN_GIFT.format(num=file_number)
    output_name_gift = input_name_gift.replace(".csv", f"{OUTPUT_SUFFIX_GIFT}")

    input_path_gift = BASE_DIR / "Data_EngGrmr" /input_name_gift
    output_path_gift = BASE_DIR / "Data_EngGrmr" / output_name_gift

    return input_path, output_path, input_path_gift, output_path_gift


def read_tab_csv(path):
    """Read TAB-delimited CSV."""
    
    with open(path, "r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")
        return list(reader)

def read_tab_csv_backup(path):
    """Read TAB CSV with optional delimiter merge."""

    normalized_data = []
    merge_empty=True
    with open(path, "r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")

        for row in reader:

            if merge_empty:
                # Remove empty columns
                row = [cell for cell in row if cell.strip() != ""]

            normalized_data.append(row)

    return normalized_data



def insert_column_header(data,fromC, max_columns, header_prefix):

    # ---- Create header row ----
    header_row = [f"{header_prefix}{i}" for i in range(fromC, max_columns + 1)]

    # ---- Insert as first row ----
    data.insert(0, header_row)
    return data


def update_column_header(data, fromC, max_columns, header_prefix):
    """
    Updates header row (row 0) from column index 'fromC'
    till 'max_columns' with names '{header_prefix}{i}'.
    """

    # ---- Safety check ----
    if not data:
        return data

    header_row = data[0]

    # ---- Ensure header row has required width ----
    if len(header_row) < max_columns:
        header_row.extend([""] * (max_columns - len(header_row)))

    # ---- Update headers from fromC onward ----
    for i in range(fromC, max_columns):
        header_row[i] = f"{header_prefix}{i}"

    return data


def write_tab_csv(path, data):
    """Write TAB-delimited CSV."""
    
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter="\t")
        writer.writerows(data)


def write_tab_csv_backup(path,data):
    """Write TAB CSV with normalized delimiters."""
    merge_empty=True
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter="\t")

        for row in data:

            if merge_empty:
                row = [cell for cell in row if cell.strip() != ""]

            writer.writerow(row)


def write_gift_file(path, data):
    """Write GIFT-formatted file."""
    
    with open(path, "w", encoding="utf-8") as f:
        for q in data:
            f.write(q + "\n")
     
def trim_empty_columns(data):
    """
    For each row in TAB-delimited data:
    - Stop reading at first empty column
    - Remove that column and everything after it
    - Return processed data
    """

    processed_data = []

    for row in data:
        new_row = []

        for cell in row:
            # Treat None, empty string, or whitespace as empty
            if cell is None or str(cell).strip() == "":
                break

            new_row.append(cell)

        processed_data.append(new_row)

    return processed_data



def remove_imagelinks(data):

    # Regex to match <img src ... />
    img_pattern = re.compile(r'<img\s+src.*?/>', re.IGNORECASE)

    for r, row in enumerate(data):
        for c, cell in enumerate(row):

            if isinstance(cell, str):
                # Remove the img tag
                cleaned = re.sub(img_pattern, '', cell)

                # Optional: strip extra whitespace left behind
                cleaned = cleaned.strip()

                data[r][c] = cleaned

    return data



