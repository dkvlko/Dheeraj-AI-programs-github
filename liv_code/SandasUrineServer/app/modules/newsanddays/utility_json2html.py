
import json
import html
from pathlib import Path


# =========================================================
# Input / Output
# =========================================================

JSON_FILE = Path(
    "/home/dkvlko/Dheeraj-AI-programs-github/"
    "liv_code/SandasUrineServer/app/modules/newsanddays/"
    "data_up1/rankednews_working.json"
)

HTML_FILE = JSON_FILE.with_suffix(".html")


# =========================================================
# Read JSON
# =========================================================

with JSON_FILE.open(
    "r",
    encoding="utf-8"
) as f:

    news_data = json.load(f)


# =========================================================
# Create HTML
# =========================================================

html_parts = [
    """<!DOCTYPE html>
<html lang="en">

<head>

<meta charset="UTF-8">

<meta name="viewport"
      content="width=device-width, initial-scale=1.0">

<title>Ranked News</title>

<style>

    body {
        font-family: Calibri, Arial, sans-serif;
        margin: 20px;
        background: #ffffff;
    }

    .news-item {
        margin-bottom: 8px;
    }

    .title {
        font-family: Calibri, Arial, sans-serif;
        font-size: 20pt;
        cursor: pointer;
        display: inline;
        color: blue;
        text-decoration: underline;
    }

    .rank {
        font-family: Calibri, Arial, sans-serif;
        font-size: 8pt;
        color: #666666;
        margin-left: 6px;
    }

    .summary {
        display: none;
        font-family: Calibri, Arial, sans-serif;
        font-size: 13pt;
        margin-top: 4px;
        margin-left: 20px;
        line-height: 1.4;
    }

</style>

<script>

    function toggleSummary(id) {

        const element = document.getElementById(id);

        if (element.style.display === "none" ||
            element.style.display === "") {

            element.style.display = "block";

        } else {

            element.style.display = "none";
        }
    }

</script>

</head>

<body>

<h1>News This Hour — {{ timestamp.strftime('%d %b %Y, %I:%M:%S %p') }}</h1>
"""
]


# =========================================================
# Add news items
# =========================================================

for index, article in enumerate(news_data):

    title = html.escape(
        str(article.get("title", ""))
    )

    summary = html.escape(
        str(article.get("summary", ""))
    )

    rank = html.escape(
        str(article.get("Rank Position", ""))
    )

    summary_id = f"summary_{index}"


    html_parts.append(
        f"""
<div class="news-item">

    <span class="title"
          onclick="toggleSummary('{summary_id}')">

        {title}

    </span>

    <span class="rank">
        [Rank {rank}]
    </span>

    <div id="{summary_id}"
         class="summary">

        {summary}

    </div>

</div>
"""
    )


# =========================================================
# Finish HTML
# =========================================================

html_parts.append(
    """
</body>
</html>
"""
)


# =========================================================
# Write HTML file
# =========================================================

with HTML_FILE.open(
    "w",
    encoding="utf-8"
) as f:

    f.write(
        "".join(html_parts)
    )


print()
print("HTML creation completed.")
print(f"Input  : {JSON_FILE}")
print(f"Output : {HTML_FILE}")
