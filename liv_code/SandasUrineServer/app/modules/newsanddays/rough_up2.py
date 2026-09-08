import feedparser
from sentence_transformers import SentenceTransformer, util
from jinja2 import Template
from dateutil import parser
import requests
import xml.etree.ElementTree as ET
import time


# =========================================================
# Configuration
# =========================================================

ABP_URL = "https://news.abplive.com/home/feed"
TOI_URL = "http://timesofindia.indiatimes.com/rssfeedstopstories.cms"

ABP_FILE = "ABPLive.rss"
TOI_FILE = "TimesOfIndia.rss"

OUTPUT_HTML = "sortednews.html"

SIMILARITY_THRESHOLD = 0.60


# =========================================================
# Download RSS files
# =========================================================

def download_rss(url, filename):

    print(f"Downloading {url}")

    response = requests.get(
        url,
        timeout=30,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )

    response.raise_for_status()

    with open(filename, "wb") as f:
        f.write(response.content)

    print(f"Saved: {filename}")

    return response.content


abp_xml = download_rss(ABP_URL, ABP_FILE)
toi_xml = download_rss(TOI_URL, TOI_FILE)


# =========================================================
# Parse RSS
# =========================================================

abp_feed = feedparser.parse(abp_xml)
toi_feed = feedparser.parse(toi_xml)

print()
print(f"ABP headlines : {len(abp_feed.entries)}")
print(f"TOI headlines : {len(toi_feed.entries)}")


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

abp_headlines = [
    entry.title.strip()
    for entry in abp_feed.entries
    if entry.get("title")
]

toi_headlines = [
    entry.title.strip()
    for entry in toi_feed.entries
    if entry.get("title")
]


# =========================================================
# Generate embeddings
# =========================================================

print("Generating embeddings...")

abp_embeddings = model.encode(
    abp_headlines,
    convert_to_tensor=True
)

toi_embeddings = model.encode(
    toi_headlines,
    convert_to_tensor=True
)


# =========================================================
# Match headlines
# =========================================================

matched_abp_titles = set()
matched_toi_titles = set()

matched_entries = []

print("\nMatching headlines...\n")


for i, abp_entry in enumerate(abp_feed.entries):

    if not abp_entry.get("title"):
        continue

    abp_title = abp_entry.title.strip()

    similarities = util.cos_sim(
        abp_embeddings[i],
        toi_embeddings
    )[0]

    best_score = float(similarities.max())

    best_index = int(similarities.argmax())

    best_toi_title = toi_headlines[best_index]


    print(f"ABP : {abp_title}")
    print(f"TOI : {best_toi_title}")
    print(f"Score: {best_score:.3f}")


    if best_score >= SIMILARITY_THRESHOLD:

        print("MATCHED\n")

        # Remember both headlines
        matched_abp_titles.add(abp_title)
        matched_toi_titles.add(best_toi_title)

        # Keep original ABP entry
        entry = dict(abp_entry)

        entry["similarity"] = best_score
        entry["matched_toi_title"] = best_toi_title

        matched_entries.append(entry)

    else:

        print("NOT MATCHED\n")


# =========================================================
# Sort matched ABP news by date
# =========================================================

def get_date(entry):

    if entry.get("published_parsed"):
        return entry.get("published_parsed")

    if entry.get("updated_parsed"):
        return entry.get("updated_parsed")

    return time.gmtime(0)


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

<h1>ABP News — Matched with Times of India</h1>

<p>
    {{ matched_entries|length }}
    matching ABP stories
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
        {{ item.matched_toi_title }}
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
# Filter RSS XML
# =========================================================

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


# =========================================================
# Remove matched headlines from both feeds
# =========================================================

print("\nFiltering RSS feeds...")

filter_rss_xml(
    abp_xml,
    matched_abp_titles,
    ABP_FILE
)

filter_rss_xml(
    toi_xml,
    matched_toi_titles,
    TOI_FILE
)


print("\n======================================")
print("Finished")
print("======================================")
print(f"HTML : {OUTPUT_HTML}")
print(f"ABP  : {ABP_FILE}")
print(f"TOI  : {TOI_FILE}")
print(f"Matched ABP stories : {len(matched_abp_titles)}")
print(f"Matched TOI stories : {len(matched_toi_titles)}")
