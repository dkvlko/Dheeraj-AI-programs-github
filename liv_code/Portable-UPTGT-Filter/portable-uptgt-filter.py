import json
import os
import sys

STATE_FILE = "data.json"
EXPORT_FILE = "export.txt"

# 👇 This will be auto-generated from your txt file
DEFAULT_LINES = []


def load_txt_file():
    txt_file = "UPTGT-KINDLE-LITERATURE.txt"

    if not os.path.exists(txt_file):
        print("ERROR: TXT file not found.")
        sys.exit(1)

    lines = []
    with open(txt_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                lines.append(line)

    return lines


def init_data():
    print("Initializing from TXT file...")
    raw_lines = load_txt_file()

    return {
        "current_index": 0,
        "lines": [{"text": l, "status": "unreviewed"} for l in raw_lines]
    }


def load_data():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        data = init_data()
        save_data(data)
        return data


def save_data(data):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def export_valid(data):
    valid = [l["text"] for l in data["lines"] if l["status"] == "valid"]

    with open(EXPORT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(valid))

    print(f"\n✅ Exported {len(valid)} lines to {EXPORT_FILE}")


def review():
    data = load_data()
    lines = data["lines"]
    i = data["current_index"]

    total = len(lines)

    print(f"\n📌 Total Questions: {total}")
    print(f"▶ Resuming from: {i+1}\n")

    while i < total:
        item = lines[i]

        if item["status"] != "unreviewed":
            i += 1
            continue

        print(f"\n[{i+1}/{total}]")
        print(item["text"])

        print("\nOptions:")
        print("y = within syllabus")
        print("n = out of syllabus")
        print("b = go back")
        print("e = export")
        print("q = quit")

        choice = input("Enter choice: ").strip().lower()

        if choice == "y":
            item["status"] = "valid"
            i += 1

        elif choice == "n":
            item["status"] = "removed"
            i += 1

        elif choice == "b":
            i = max(0, i - 1)

        elif choice == "e":
            export_valid(data)

        elif choice == "q":
            break

        else:
            print("Invalid input")
            continue

        data["current_index"] = i
        save_data(data)

    print("\n💾 Progress saved.")


if __name__ == "__main__":
    review()
