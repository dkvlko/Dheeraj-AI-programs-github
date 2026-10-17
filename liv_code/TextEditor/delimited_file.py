import sys
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

class CsvEditor:
    def __init__(self, root, filepath, delimiter):
        self.root = root
        self.filepath = filepath
        self.delimiter = delimiter

        self.data, self.col_count = self.load_file()

        self.tree = ttk.Treeview(
            root,
            columns=[f"C{i}" for i in range(self.col_count)],
            show="headings",
            selectmode="extended"
        )

        for i in range(self.col_count):
            self.tree.heading(f"C{i}", text=f"Col {i+1}")
            self.tree.column(f"C{i}", width=140, anchor="w")

        for row in self.data:
            self.tree.insert("", "end", values=row)

        self.tree.pack(fill="both", expand=True)

        self.tree.bind("<Double-1>", self.edit_cell)
        self.root.bind("<Delete>", self.delete_rows)
        self.root.bind("<Control-n>", self.add_row)
        self.root.bind("<Control-N>", self.add_column)
        self.root.bind("<Control-D>", self.delete_column)
        self.root.bind("<Control-s>", self.save)
        self.root.bind("<Control-q>", lambda e: root.destroy())

    def load_file(self):
        rows = []
        max_cols = 1

        with open(self.filepath, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.rstrip("\n")
                cols = line.split(self.delimiter) if self.delimiter else [line]
                rows.append(cols)
                max_cols = max(max_cols, len(cols))

        for r in rows:
            while len(r) < max_cols:
                r.append("")

        return rows, max_cols

    def edit_cell(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            return

        row_id = self.tree.identify_row(event.y)
        col = self.tree.identify_column(event.x)

        x, y, w, h = self.tree.bbox(row_id, col)
        value = self.tree.set(row_id, col)

        entry = tk.Entry(self.tree)
        entry.place(x=x, y=y, width=w, height=h)
        entry.insert(0, value)
        entry.focus()

        def save_edit(e):
            self.tree.set(row_id, col, entry.get())
            entry.destroy()

        entry.bind("<Return>", save_edit)
        entry.bind("<FocusOut>", save_edit)

    def add_row(self, event=None):
        self.tree.insert("", "end", values=[""] * self.col_count)

    def delete_rows(self, event=None):
        for row in self.tree.selection():
            self.tree.delete(row)

    def add_column(self, event=None):
        self.col_count += 1
        col_id = f"C{self.col_count-1}"
        self.tree["columns"] = self.tree["columns"] + (col_id,)

        self.tree.heading(col_id, text=f"Col {self.col_count}")
        self.tree.column(col_id, width=140)

        for row in self.tree.get_children():
            values = list(self.tree.item(row, "values"))
            values.append("")
            self.tree.item(row, values=values)

    def delete_column(self, event=None):
        if self.col_count <= 1:
            messagebox.showwarning("Warning", "Cannot delete last column")
            return

        self.col_count -= 1
        self.tree["columns"] = self.tree["columns"][:-1]

        for row in self.tree.get_children():
            values = list(self.tree.item(row, "values"))[:-1]
            self.tree.item(row, values=values)

    def save(self, event=None):
        with open(self.filepath, "w", encoding="utf-8") as f:
            for row in self.tree.get_children():
                values = self.tree.item(row, "values")
                line = self.delimiter.join(values) if self.delimiter else values[0]
                f.write(line + "\n")

        messagebox.showinfo("Saved", "File saved successfully")


def main():
    if len(sys.argv) < 2:
        print("Usage: python mini_csv_editor.py <file> [delimiter]")
        sys.exit(1)

    filepath = Path(sys.argv[1])
    delimiter = sys.argv[2] if len(sys.argv) > 2 else None

    if not filepath.exists():
        print("File not found")
        sys.exit(1)

    root = tk.Tk()
    root.title(f"Mini CSV Editor – {filepath.name}")

    CsvEditor(root, filepath, delimiter)
    root.mainloop()


if __name__ == "__main__":
    main()
