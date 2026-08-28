#!/usr/bin/env python3

import json
import html
import sys


def json_to_html(data, level=0):
    """Convert a Python JSON structure into readable HTML."""

    if isinstance(data, dict):
        if not data:
            return '<span class="empty">{}</span>'

        parts = ['<div class="object">']

        for key, value in data.items():
            key_html = html.escape(str(key))

            parts.append(
                '<div class="entry">'
                f'<span class="key">{key_html}</span>'
                f'{json_to_html(value, level + 1)}'
                '</div>'
            )

        parts.append('</div>')
        return '\n'.join(parts)

    elif isinstance(data, list):
        if not data:
            return '<span class="empty">[]</span>'

        parts = ['<div class="array">']

        for index, value in enumerate(data):
            parts.append(
                '<div class="array-entry">'
                f'<span class="index">[{index}]</span>'
                f'{json_to_html(value, level + 1)}'
                '</div>'
            )

        parts.append('</div>')
        return '\n'.join(parts)

    elif isinstance(data, str):
        return (
            '<span class="string">'
            + html.escape(data)
            + '</span>'
        )

    elif isinstance(data, bool):
        return (
            '<span class="boolean">'
            + str(data).lower()
            + '</span>'
        )

    elif data is None:
        return '<span class="null">null</span>'

    elif isinstance(data, (int, float)):
        return (
            '<span class="number">'
            + str(data)
            + '</span>'
        )

    else:
        return (
            '<span class="unknown">'
            + html.escape(str(data))
            + '</span>'
        )


def create_html(json_data, title="JSON Viewer"):
    """Create the complete HTML document."""

    body = json_to_html(json_data)

    return f"""<!DOCTYPE html>
<html lang="en">

<head>
<meta charset="UTF-8">

<title>{html.escape(title)}</title>

<style>

body {{
    font-family: Arial, sans-serif;
    background: #f5f5f5;
    color: #222;
    margin: 0;
    padding: 20px;
}}

h1 {{
    margin-top: 0;
}}

.container {{
    background: white;
    padding: 20px;
    border-radius: 8px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}}

.object {{
    margin-left: 20px;
    border-left: 2px solid #ddd;
    padding-left: 12px;
}}

.array {{
    margin-left: 20px;
    border-left: 2px solid #ccc;
    padding-left: 12px;
}}

.entry {{
    margin: 6px 0;
}}

.array-entry {{
    margin: 6px 0;
}}

.key {{
    font-weight: bold;
    color: #005cc5;
    margin-right: 10px;
}}

.index {{
    color: #777;
    font-weight: bold;
    margin-right: 10px;
}}

.string {{
    color: #008000;
    white-space: pre-wrap;
}}

.number {{
    color: #aa5500;
}}

.boolean {{
    color: #990099;
    font-weight: bold;
}}

.null {{
    color: #999;
    font-style: italic;
}}

.empty {{
    color: #777;
    font-style: italic;
}}

button {{
    padding: 8px 14px;
    margin-bottom: 15px;
    cursor: pointer;
}}

</style>

<script>

function toggleAll() {{

    const elements = document.querySelectorAll(
        '.object, .array'
    );

    elements.forEach(function(element) {{

        if (element.style.display === 'none') {{
            element.style.display = '';
        }} else {{
            element.style.display = 'none';
        }}

    }});
}}

</script>

</head>

<body>

<div class="container">

<h1>{html.escape(title)}</h1>

<button onclick="toggleAll()">
    Expand / Collapse
</button>

<div id="json">
{body}
</div>

</div>

</body>

</html>
"""


def main():

    if len(sys.argv) != 3:
        print(
            "Usage:\n"
            "    python3 json_to_html.py input.json output.html"
        )
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]

    try:
        with open(input_file, "r", encoding="utf-8") as f:
            data = json.load(f)

    except FileNotFoundError:
        print(f"Error: file not found: {input_file}")
        sys.exit(1)

    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON: {e}")
        sys.exit(1)

    title = input_file

    html_output = create_html(data, title)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html_output)

    print(f"HTML file created: {output_file}")


if __name__ == "__main__":
    main()
