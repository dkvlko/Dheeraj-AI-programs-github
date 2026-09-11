
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
import json
from datetime import datetime
import shutil
import numpy as np




# =========================================================
# Configuration
# =========================================================


# Copy used for processing

FOUTPUT_JSON = Path(
        "/home/dkvlko/Dheeraj-AI-programs-github/"
        "liv_code/SandasUrineServer/app/modules/newsanddays/data_up1/rankednews_working.json"
     )   

FINPUT_JSON = Path(
        "/home/dkvlko/Dheeraj-AI-programs-github/"
        "liv_code/SandasUrineServer/app/modules/newsanddays/data_up1/rankednews.json"
     )   

SIMILARITY_THRESHOLD = 0.70


model = SentenceTransformer(
        "sentence-transformers/all-MiniLM-L6-v2",
        device="cpu" )

# =========================================================
# Process news
# =========================================================


# -----------------------------------------------------
# Read current ranked JSON
# -----------------------------------------------------

with FINPUT_JSON.open(
    "r",
    encoding="utf-8"
) as f:

    news_data = json.load(f)

# -----------------------------------------------------
# Check JSON structure
# -----------------------------------------------------

if not isinstance(news_data, list):

    raise ValueError(
        "FINPUT_JSON must contain a JSON list of news items."
    )

# -----------------------------------------------------
# Total number of news items
# -----------------------------------------------------

total_items = len(news_data)

# Current number of items being processed
current_items = total_items

print()
print("=" * 60)
print(f"Total items : {total_items}")

# -----------------------------------------------------
# Stop when only one item remains
# -----------------------------------------------------


# -----------------------------------------------------
# Create a fresh copy of the input JSON
# -----------------------------------------------------

shutil.copy2(
    FINPUT_JSON,
    FOUTPUT_JSON
)

# -----------------------------------------------------
# Read the copied JSON
# -----------------------------------------------------

with FOUTPUT_JSON.open(
    "r",
    encoding="utf-8"
) as f:

    second_data = json.load(f)

while current_items > 1 :


    # -----------------------------------------------------
    # Remove first news item from second JSON
    # -----------------------------------------------------

    first_news = second_data.pop(0)

    # First item has now been removed
    current_items -= 1

    first_title = first_news.get("title")

    if not first_title:

        print(
            "First news item has no title. "
            "Stopping."
        )

        break

    first_title = str(first_title)

    print(f"Processing : {first_title}")

    # -----------------------------------------------------
    # If nothing remains after removing first item
    # -----------------------------------------------------

    if not second_data:

        # Put first item back
        second_data.append(first_news)

        total_items = 1

        with FOUTPUT_JSON.open(
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                second_data,
                f,
                ensure_ascii=False,
                indent=4
            )

        shutil.copy2(
            FOUTPUT_JSON,
            FINPUT_JSON
        )

        print("Only one item remains.")
        break

    # =====================================================
    # Create title list from remaining news
    # =====================================================

    second_titles = []

    valid_items = []

    for item in second_data:

        title = item.get("title")

        if title:

            second_titles.append(
                str(title)
            )

            valid_items.append(item)

    # -----------------------------------------------------
    # Encode first title
    # -----------------------------------------------------

    first_embedding = model.encode(
        [first_title],
        convert_to_numpy=True,
        normalize_embeddings=True
    )

    # -----------------------------------------------------
    # Encode all remaining titles
    # -----------------------------------------------------

    second_embeddings = model.encode(
        second_titles,
        convert_to_numpy=True,
        normalize_embeddings=True
    )

    # -----------------------------------------------------
    # Calculate similarity
    #
    # Because embeddings are normalized, dot product
    # gives cosine similarity.
    # -----------------------------------------------------

    similarities = np.dot(
        second_embeddings,
        first_embedding[0]
    )

    # =====================================================
    # Delete matching news items
    # =====================================================

    items_deleted = 0

    remaining_data = []

    title_index = 0

    for item in second_data:

        title = item.get("title")

        # -------------------------------------------------
        # Keep items without a title
        # -------------------------------------------------

        if not title:

            remaining_data.append(item)

            continue

        similarity = similarities[title_index]

        title_index += 1

        # -------------------------------------------------
        # Delete if similarity >= 70%
        # -------------------------------------------------

        if similarity >= SIMILARITY_THRESHOLD:

            items_deleted += 1

            print(
                f"Deleted ({similarity:.2%}) : "
                f"{title}"
            )

        else:

            remaining_data.append(item)

    # =====================================================
    # Append the first news item to the end
    # =====================================================
    current_items -= items_deleted
    
    remaining_data.append(
        first_news
    )

    # =====================================================
    # Update total_items
    # =====================================================

    #total_items = total_items - items_deleted

    # -----------------------------------------------------
    # IMPORTANT:
    #
    # We removed the first item from the working file,
    # then deleted matching items, but finally appended
    # that first item back.
    #
    # Therefore the actual number of items in the final
    # JSON is:
    #
    # original total - items_deleted
    # -----------------------------------------------------

    actual_total_items = len(
        remaining_data
    )

    # -----------------------------------------------------
    # Sanity check
    # -----------------------------------------------------

    #if actual_total_items != total_items:

     #   raise RuntimeError(
      #      f"Count mismatch: calculated "
      #      f"{total_items}, but JSON contains "
      #      f"{actual_total_items} items."
      #  )

    # =====================================================
    # Write processed second JSON
    # =====================================================

    with FOUTPUT_JSON.open(
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            remaining_data,
            f,
            ensure_ascii=False,
            indent=4
        )

    # =====================================================
    # Overwrite first JSON
    # =====================================================

    shutil.copy2(
        FOUTPUT_JSON,
        FINPUT_JSON
    )

    # =====================================================
    # Report
    # =====================================================

    print()
    print(f"Items deleted : {items_deleted}")
    print(f"Current items   : {current_items}")
    print(f"Output        : {FINPUT_JSON}")

    # -----------------------------------------------------
    # Stop if one item remains
    # -----------------------------------------------------

    if current_items <= 1:

        print()
        print("Only one news item remains.")
        print("Processing completed.")

        break
