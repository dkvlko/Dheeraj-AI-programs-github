import csv
from config import BASE_DIR, INPUT_PATTERN, INPUT_PATTERN_GIFT, OUTPUT_SUFFIX, OUTPUT_SUFFIX_GIFT


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


def read_tab_csv_backup(path):
    """Read TAB-delimited CSV."""
    
    with open(path, "r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")
        return list(reader)

def read_tab_csv(path):
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


def write_tab_csv_backup(path, data):
    """Write TAB-delimited CSV."""
    
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter="\t")
        writer.writerows(data)


def write_tab_csv(path,data):
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
     
