import feedparser
from sentence_transformers import SentenceTransformer, util
from jinja2 import Template
import time

# ---------------------------------------------------------
# RSS sources
# ---------------------------------------------------------

ABP_RSS = "https://news.abplive.com/home/feed"

TOI_RSS = "http://timesofindia.indiatimes.com/rssfeedstopstories.cms"

OUTPUT_FILE = "sortednews.html"

SIMILARITY_THRESHOLD = 0.60


# ---------------------------------------------------------
# Load semantic model
# ---------------------------------------------------------

print("Loading Sentence Transformer model...")

#model = SentenceTransformer("all-MiniLM-L6-v2")
model = SentenceTransformer(
    "sentence-transformers/all-MiniLM-L6-v2",
    device="cpu"
)


# ---------------------------------------------------------
# Read RSS feeds
# ---------------------------------------------------------

print("Reading ABP RSS...")

abp_feed = feedparser.parse(ABP_RSS)

print("Reading Times of India RSS...")

toi_feed = feedparser.parse(TOI_RSS)

print(f"ABP headlines : {len(abp_feed.entries)}")
print(f"TOI headlines : {len(toi_feed.entries)}")


# ---------------------------------------------------------
# Extract headlines
# ---------------------------------------------------------

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


# ---------------------------------------------------------
# Generate embeddings
# ---------------------------------------------------------

print("Generating embeddings...")

abp_embeddings = model.encode(
    abp_headlines,
    convert_to_tensor=True
)

toi_embeddings = model.encode(
    toi_headlines,
    convert_to_tensor=True
)


# ---------------------------------------------------------
# Match ABP headlines against TOI headlines
# ---------------------------------------------------------

matched_entries = []

print("\nMatching headlines...\n")

for i, abp_entry in enumerate(abp_feed.entries):

    if not abp_entry.get("title"):
        continue

    abp_title = abp_entry.title.strip()

    # Find similarity against ALL TOI headlines
    similarities = util.cos_sim(
        abp_embeddings[i],
        toi_embeddings
    )[0]

    # Highest similarity
    best_score = float(similarities.max())

    best_index = int(similarities.argmax())

    best_toi_title = toi_headlines[best_index]

    print(f"ABP : {abp_title}")
    print(f"TOI : {best_toi_title}")
    print(f"Score: {best_score:.3f}")

    if best_score >= SIMILARITY_THRESHOLD:

        # Store the ORIGINAL ABP RSS entry
        # and add matching information
        entry = dict(abp_entry)

        entry["similarity"] = best_score
        entry["matched_toi_title"] = best_toi_title

        matched_entries.append(entry)

        print("MATCHED\n")

    else:
        print("NOT MATCHED\n")


# ---------------------------------------------------------
# Sort matched ABP news by publication time
# ---------------------------------------------------------


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


# ---------------------------------------------------------
# Jinja template
# ---------------------------------------------------------

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
    ABP headlines matched with Times of India
    (similarity ≥ {{ threshold }})
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

        Semantic similarity with TOI:
        <strong>
            {{ "%.1f"|format(item.similarity * 100) }}%
        </strong>

    </small>

    <br>

    <small>

        Matching TOI headline:
        {{ item.matched_toi_title }}

    </small>

    <hr>

</article>

{% endfor %}


</body>
</html>
""")


# ---------------------------------------------------------
# Generate HTML
# ---------------------------------------------------------

html = template.render(
    matched_entries=matched_entries,
    threshold=SIMILARITY_THRESHOLD
)


with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    f.write(html)


print("===================================")
print(f"Created: {OUTPUT_FILE}")
print(f"Matched headlines: {len(matched_entries)}")
print("===================================")
