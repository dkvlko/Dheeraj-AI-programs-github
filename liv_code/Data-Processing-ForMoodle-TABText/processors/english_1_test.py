# processors/english_2.py

def process(data):

    for row in data:
        if len(row) >= 3:
            row[2] = row[2].upper()

    return data
