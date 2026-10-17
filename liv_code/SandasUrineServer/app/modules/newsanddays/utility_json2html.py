import shutil
import json
import html
from pathlib import Path
from datetime import datetime

# =========================================================
# Input / Output
# =========================================================

JSON_FILE = Path(
    "/home/dkvlko/Dheeraj-AI-programs-github/"
    "liv_code/SandasUrineServer/app/modules/newsanddays/"
    "data/rankednews_working.json"
)

HTML_FILE = JSON_FILE.with_suffix(".html")

def json2html() :
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

    timestamp = datetime.now().strftime('%d %b %Y, %I:%M:%S %p')

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
            margin: 10px;
            background: #ffffff;
        }

        .news-item {
            margin-bottom: 8px;
        }

        .title {
            font-family: Calibri, Arial, sans-serif;
            font-size: 35pt;
            cursor: pointer;
            display: inline;
            color: blue;
            text-decoration: underline;
            margin-bottom: 4px;
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
            font-size: 15pt;
            margin-top: 4px;
            margin-left: 20px;
            line-height: 1.4;
        }
    .news-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        width: 100%;
    }

    .news-button {
        width: 96px;
        height: 48px;
        font-size: 14px;
        cursor: pointer;
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
    """,f"""
    <div class="news-header">
        <h1>News This Hour — {timestamp}</h1>

        <button class="news-button" onclick="history.back()">
           Back 
        </button>
    </div>
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

        published = html.escape(
            str(article.get("published", ""))
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

        <span class="rank">
            [ {published}]
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

    html_output = "".join(html_parts)
    # =========================================================
    # Write HTML file
    # =========================================================

    with HTML_FILE.open(
        "w",
        encoding="utf-8"
    ) as f:

        f.write(html_output)


    #print()
    #print("HTML creation completed.")
    #print(f"Input  : {JSON_FILE}")
    #print(f"Output : {HTML_FILE}")

    source = Path("/home/dkvlko/Dheeraj-AI-programs-github/liv_code/SandasUrineServer/app/modules/newsanddays/data/rankednews_working.html")
    destination = Path("/home/dkvlko/Dheeraj-AI-programs-github/liv_code/SandasUrineServer/app/modules/clock_lap/templates/details_date.html")
    shutil.copy2(source,destination)

def main() :
    json2html()

if __name__ == "__main__" :
    main()

