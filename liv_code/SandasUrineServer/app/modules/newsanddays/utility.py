
import feedparser
from sentence_transformers import SentenceTransformer, util
from jinja2 import Template
from dateutil import parser
import requests
import xml.etree.ElementTree as ET
import time
from pathlib import Path
from urllib.parse import urlparse
import requests

# =========================================================
# Configuration
# =========================================================



OUTPUT_HTML = "data/sortednews.html"

OUTPUT_JSON = "data/sortednews.json"

SIMILARITY_THRESHOLD = 0.60




def greet_user(name):
    return f"Hello, {name}! Welcome to Python."

def filter_rss_xml(xml_data, titles_to_remove, output_file):

    """
    Remove <item> elements whose <title> is in titles_to_remove.
    """

    root = ET.fromstring(xml_data)

    removed = 0

    # Find all item elements, regardless of RSS namespace
    for parent in root.iter():

        for item in list(parent):

            # RSS item
            if item.tag.split("}")[-1] != "item":
                continue

            title_element = None

            for child in item:

                if child.tag.split("}")[-1] == "title":
                    title_element = child
                    break

            if title_element is None:
                continue

            title = (title_element.text or "").strip()

            if title in titles_to_remove:

                parent.remove(item)

                removed += 1


    # Write modified RSS
    tree = ET.ElementTree(root)

    tree.write(
        output_file,
        encoding="utf-8",
        xml_declaration=True
    )

    print(
        f"Removed {removed} headlines -> {output_file}"
    )

def get_date(entry):

    if entry.get("published_parsed"):
        return entry.get("published_parsed")

    if entry.get("updated_parsed"):
        return entry.get("updated_parsed")

    return time.gmtime(0)

def processURLs(rssa,rssb) :

# Get File Contents #
    with rssa.open("rb") as f:
        # f is a file handle
        content = f.read()

    rssa_xml = content

    with rssb.open("rb") as f:
        # f is a file handle
        content = f.read()

    rssb_xml = content
# =========================================================
# Parse RSS
# =========================================================

    rssa_feed = feedparser.parse(rssa_xml)
    rssb_feed = feedparser.parse(rssb_xml)

# =========================================================
# Load Sentence Transformer
# =========================================================

    print("\nLoading Sentence Transformer model...")

    #model = SentenceTransformer("all-MiniLM-L6-v2")


    model = SentenceTransformer(
        "sentence-transformers/all-MiniLM-L6-v2",
        device="cpu"
    )
    


    # =========================================================
    # Extract headlines
    # =========================================================

    rssa_headlines = [
        entry.title.strip()
        for entry in rssa_feed.entries
        if entry.get("title")
    ]

    rssb_headlines = [
        entry.title.strip()
        for entry in rssb_feed.entries
        if entry.get("title")
    ]


    # =========================================================
    # Generate embeddings
    # =========================================================

    print("Generating embeddings...")

    rssa_embeddings = model.encode(
        rssa_headlines,
        convert_to_tensor=True
    )

    rssb_embeddings = model.encode(
        rssb_headlines,
        convert_to_tensor=True
    )


    # =========================================================
    # Match headlines
    # =========================================================

    matched_rssa_titles = set()
    matched_rssb_titles = set()

    matched_entries = []

    print("\nMatching headlines...\n")


    for i, rssa_entry in enumerate(rssa_feed.entries):

        if not rssa_entry.get("title"):
            continue

        rssa_title = rssa_entry.title.strip()

        similarities = util.cos_sim(
            rssa_embeddings[i],
            rssb_embeddings
        )[0]

        best_score = float(similarities.max())

        best_index = int(similarities.argmax())

        best_rssb_title = rssb_headlines[best_index]


        print(f"RSSA : {rssa_title}")
        print(f"RSSB : {best_rssb_title}")
        print(f"Score: {best_score:.3f}")


        if best_score >= SIMILARITY_THRESHOLD:

            print("MATCHED\n")

            # Remember both headlines
            matched_rssa_titles.add(rssa_title)
            matched_rssb_titles.add(best_rssb_title)

            # Keep original ABP entry
            entry = dict(rssa_entry)

            entry["similarity"] = best_score
            entry["matched_rssb_title"] = best_rssb_title

            matched_entries.append(entry)

        else:

            print("NOT MATCHED\n")


    matched_entries.sort(
        key=get_date,
        reverse=True
    )


    # =========================================================
    # Generate sortednews.html
    # =========================================================

    template = Template("""
    <!DOCTYPE html>
    <html>

    <head>

        <meta charset="UTF-8">

        <meta name="viewport"
              content="width=device-width, initial-scale=1.0">

        <title>Sorted News</title>

    </head>

    <body>

    <h1>RSSA News — Matched with RSSB</h1>

    <p>
        {{ matched_entries|length }}
        matching RSSA stories
    </p>

    {% for item in matched_entries %}

    <article>

        <h2>
            <a href="{{ item.link }}" target="_blank">
                {{ item.title }}
            </a>
        </h2>

        {% if item.get("published") %}

            <small>
                {{ item.published }}
            </small>

        {% elif item.get("updated") %}

            <small>
                {{ item.updated }}
            </small>

        {% endif %}

        {% if item.get("summary") %}

            <p>
                {{ item.summary|safe }}
            </p>

        {% endif %}

        <small>
            Similarity:
            {{ "%.1f"|format(item.similarity * 100) }}%
        </small>

        <br>

        <small>
            TOI:
            {{ item.matched_rssb_title }}
        </small>

        <hr>

    </article>

    {% endfor %}

    </body>
    </html>
    """)


    html = template.render(
        matched_entries=matched_entries
    )


    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)


    print(f"\nCreated: {OUTPUT_HTML}")


    # =========================================================
    # Remove matched headlines from both feeds
    # =========================================================

    print("\nFiltering RSS feeds...")

    filter_rss_xml(
        rssa_xml,
        matched_rssa_titles,
        rssa
    )

    filter_rss_xml(
        rssb_xml,
        matched_rssb_titles,
        rssb
    )


    print("\n======================================")
    print("Finished")
    print("======================================")
    print(f"HTML : {OUTPUT_HTML}")
    print(f"RSSA  : {rssa}")
    print(f"RSSB  : {rssb}")
    print(f"Matched RSSA stories : {len(matched_rssa_titles)}")
    print(f"Matched RSSB stories : {len(matched_rssb_titles)}")

def download_rss(urls, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    files = []

    for url in urls:
        parsed = urlparse(url)

        # Use the domain as the filename
        site = parsed.netloc.removeprefix("www.")
        filename = output_dir / f"{site}.rss"

        response = requests.get(url, timeout=30)
        response.raise_for_status()

        filename.write_bytes(response.content)
        files.append(filename)

    return files

# The main function where the core logic of the script lives
def main():
    urls = [
    "https://news.abplive.com/home/feed",
    "http://timesofindia.indiatimes.com/rssfeedstopstories.cms",
    "https://www.thehindu.com/feeder/default.rss",
    ]
    #ABP_URL = "https://news.abplive.com/home/feed"
    #TOI_URL = "http://timesofindia.indiatimes.com/rssfeedstopstories.cms"
    rss_files = download_rss(urls, "data")
    for i in range(len(rss_files) - 1):
        for j in range(i + 1, len(rss_files
            processURLs(rss_files[i], rss_files[j])
    #processURLs(rss_files[0],rss_files[1])


if __name__ == "__main__":
    main()
