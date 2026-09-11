
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



#OUTPUT_HTML = "data_up1/sortednews.html"

OUTPUT_JSON = "data_up1/sortednews.json"

INPUT_JSON = OUTPUT_JSON

FINPUT_JSON = Path("/home/dkvlko/Dheeraj-AI-programs-github/"
        "liv_code/SandasUrineServer/app/modules/newsanddays/data_up1/sortednews.json")

Common_Json = Path(
        "/home/dkvlko/Dheeraj-AI-programs-github/"
        "liv_code/SandasUrineServer/app/modules/newsanddays/data_up1/common.json"
     )   

Ranked_Json = Path(
        "/home/dkvlko/Dheeraj-AI-programs-github/"
        "liv_code/SandasUrineServer/app/modules/newsanddays/data_up1/rankednews.json"
     )   

SIMILARITY_THRESHOLD = 0.70



model = SentenceTransformer(
        "sentence-transformers/all-MiniLM-L6-v2",
        device="cpu" )

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

    #print(f"Removed {removed} headlines -> {output_file}")

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

    #print("\nLoading Sentence Transformer model...")

    #model = SentenceTransformer("all-MiniLM-L6-v2")


    


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

    if not rssa_headlines or not rssb_headlines:

        #print("\nHeadlines are missing from the file.")

        if not rssa_headlines:
            print(f"RSSA: {rssa}")

        if not rssb_headlines:
            print(f"RSSB: {rssb}")

        return

    # =========================================================
    # Generate embeddings
    # =========================================================

    #print("Generating embeddings...")

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

    #print("\nMatching headlines...\n")


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


        #print(f"RSSA : {rssa_title}")
        #print(f"RSSB : {best_rssb_title}")
        #print(f"Score: {best_score:.3f}")


        if best_score >= SIMILARITY_THRESHOLD:

            #print("MATCHED\n")

            # Remember both headlines
            matched_rssa_titles.add(rssa_title)
            matched_rssb_titles.add(best_rssb_title)

            # Keep original ABP entry
            entry = dict(rssa_entry)

            entry["similarity"] = best_score
            entry["matched_rssb_title"] = best_rssb_title

            matched_entries.append(entry)

        #else:

            #print("NOT MATCHED\n")


    matched_entries.sort(
        key=get_date,
        reverse=True
    )


    # =========================================================
    # Generate sortednews.json
    # =========================================================

    # Read existing data
    if Path(OUTPUT_JSON).exists():
        try:
            with open(OUTPUT_JSON, "r", encoding="utf-8") as f:
                sorted_news = json.load(f)

            if not isinstance(sorted_news, list):
                sorted_news = []

        except (json.JSONDecodeError, OSError):
            sorted_news = []

    else:
        sorted_news = []


    # Append newly matched entries
    sorted_news.extend(matched_entries)


    # Save updated JSON
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(
            sorted_news,
            f,
            ensure_ascii=False,
            indent=2
        )


    #print(f"\nUpdated: {OUTPUT_JSON}")
    #print(f"Total stories: {len(sorted_news)}")

    # =========================================================
    # Remove matched headlines from both feeds
    # =========================================================

    #print("\nFiltering RSS feeds...")

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


    #print("\n======================================")
    #print("Finished")
    #print("======================================")
    #print(f"RSSA  : {rssa}")
    #print(f"RSSB  : {rssb}")
    #print(f"Matched RSSA stories : {len(matched_rssa_titles)}")
    #print(f"Matched RSSB stories : {len(matched_rssb_titles)}")

def download_rss(urls, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/140.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "application/rss+xml, application/xml, "
            "text/xml, */*;q=0.8"
        ),
    }

    files = []

    for url in urls:
        parsed = urlparse(url)

        # Use the domain as the filename
        site = parsed.netloc.removeprefix("www.")
        filename = output_dir / f"{site}.rss"

        response = requests.get(url,
                                headers = headers,
                                timeout=30)

        response.raise_for_status()

        filename.write_bytes(response.content)
        files.append(filename)

    return files


def combine_rss_files(rss_files):
    channel_items = []
    
    output_file = Path("/home/dkvlko/Dheeraj-AI-programs-github/liv_code/SandasUrineServer/app/modules/newsanddays//data_up1/common.rss")

    for rss_file in rss_files:
        try:
            tree = ET.parse(rss_file)
            root = tree.getroot()

            channel = root.find("channel")

            if channel is None:
                print(f"Skipping invalid RSS file: {rss_file}")
                continue

            for item in channel.findall("item"):
                channel_items.append(item)

        except (OSError, ET.ParseError) as e:
            print(f"Could not process {rss_file}: {e}")

    # Create combined RSS
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")

    ET.SubElement(channel, "title").text = "Common RSS"
    ET.SubElement(channel, "description").text = "Combined RSS feed"
    ET.SubElement(channel, "link").text = ""

    for item in channel_items:
        channel.append(item)

    tree = ET.ElementTree(rss)
    tree.write(output_file, encoding="utf-8", xml_declaration=True)
    
    return output_file

def processRanking(
        Sorted_Json: Path,
        Common_Json: Path
    ) -> None:
        """
        Semantically match titles in Sorted_Json against every title
        in Common_Json.

        A cosine similarity >= 0.70 is considered a match.

        For every Sorted_Json article having at least one match:

            - copy the complete Sorted_Json article
            - add "count"
            - add "best_similarity"
            - add "best_matched_title"

        The result is saved as rankednews.json in the same directory
        as Sorted_Json.
        """

        # ---------------------------------------------------------
        # Read Sorted_Json
        # ---------------------------------------------------------

        with Sorted_Json.open("r", encoding="utf-8") as f:
            sorted_data = json.load(f)

        # ---------------------------------------------------------
        # Read Common_Json
        # ---------------------------------------------------------

        with Common_Json.open("r", encoding="utf-8") as f:
            common_data = json.load(f)


        # ---------------------------------------------------------
        # Extract titles
        # ---------------------------------------------------------

        sorted_titles = [
            str(article["title"])
            for article in sorted_data
            if article.get("title")
        ]

        common_titles = [
            str(article["title"])
            for article in common_data
            if article.get("title")
        ]

        if not sorted_titles:
            raise ValueError(
                "No titles found in Sorted_Json."
            )

        if not common_titles:
            raise ValueError(
                "No titles found in Common_Json."
            )


        # ---------------------------------------------------------
        # Encode all titles in batches
        #
        # normalize_embeddings=True means:
        #
        # cosine_similarity(A, B)
        #
        # is simply:
        #
        # A @ B.T
        # ---------------------------------------------------------

        sorted_embeddings = model.encode(
            sorted_titles,
            batch_size=32,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=True
        )

        common_embeddings = model.encode(
            common_titles,
            batch_size=32,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=True
        )

        # ---------------------------------------------------------
        # Calculate ALL similarities at once
        #
        # Shape:
        #
        # sorted_embeddings = N x 384
        # common_embeddings = M x 384
        #
        # result             = N x M
        # ---------------------------------------------------------

        similarity_matrix = (
            sorted_embeddings @ common_embeddings.T
        )

        # ---------------------------------------------------------
        # Create ranked results
        # ---------------------------------------------------------

        ranked_entries = []

        sorted_title_index = 0

        for article in sorted_data:

            title = article.get("title")

            if not title:
                continue

            title = str(title)

            similarities = similarity_matrix[
                sorted_title_index
            ]

            sorted_title_index += 1

            # -----------------------------------------------------
            # Find every Common_Json title matching >= 70%
            # -----------------------------------------------------

            matching_indices = np.flatnonzero(
                similarities >= SIMILARITY_THRESHOLD 
            )

            # -----------------------------------------------------
            # No match
            # -----------------------------------------------------

            if len(matching_indices) == 0:
                continue

            # -----------------------------------------------------
            # Copy complete Sorted_Json article
            # -----------------------------------------------------

            ranked_article = dict(article)

            # -----------------------------------------------------
            # Count number of Common_Json matches
            # -----------------------------------------------------

            ranked_article["count"] = int(
                len(matching_indices)
            )

            # -----------------------------------------------------
            # Best match information
            # -----------------------------------------------------

            best_index = int(
                np.argmax(similarities)
            )

            ranked_article["best_similarity"] = float(
                similarities[best_index]
            )

            ranked_article["best_matched_title"] = (
                common_titles[best_index]
            )

            ranked_entries.append(ranked_article)

    # ---------------------------------------------------------
    # Sort by count — highest count first
    # ---------------------------------------------------------

        ranked_entries.sort(
            key=lambda article: article["count"],
            reverse=True
        )
        # ---------------------------------------------------------
        # Add Rank Position
        # ---------------------------------------------------------

        for rank_position, article in enumerate(
            ranked_entries,
            start=1
        ):
            article["Rank Position"] = rank_position

        # ---------------------------------------------------------
        # Output file
        # ---------------------------------------------------------

        #ranked_json = (
        #    Sorted_Json.parent / "rankednews.json"
        #)

        # ---------------------------------------------------------
        # Write JSON
        # ---------------------------------------------------------

        with Ranked_Json.open(
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                ranked_entries,
                f,
                ensure_ascii=False,
                indent=4
            )

        print()
        print("Ranking completed.")
        print(f"Sorted articles : {len(sorted_data)}")
        print(f"Common articles : {len(common_data)}")
        print(f"Ranked articles : {len(ranked_entries)}")
        print(f"Output          : {Ranked_Json}")
        

def rss_to_json(rssa) :
        
    with rssa.open("rb") as f:
        # f is a file handle
        content = f.read()

    rssa_xml = content

# =========================================================
# Parse RSS
# =========================================================

    rssa_feed = feedparser.parse(rssa_xml)

    with open(Common_Json,"w",encoding="utf-8") as f:
        json.dump(
                rssa_feed.entries,
                f,
                ensure_ascii=False,
                indent=2,
                default=str
        )


        
# The main function where the core logic of the script lives
def main():
    urls = [
    "https://news.abplive.com/home/feed",
    "http://timesofindia.indiatimes.com/rssfeedstopstories.cms",
    "https://www.thehindu.com/feeder/default.rss",
    "https://www.hindustantimes.com/feeds/rss/latest/rssfeed.xml",
    "https://feeds.feedburner.com/ndtvnews-top-stories",
    "https://www.indiatoday.in/rss/home",
    "https://www.news18.com/commonfeeds/v1/eng/rss/india.xml",
    "https://www.livemint.com/rss/news",
    ]

    data_dir = Path("./data_up1")

    for path in data_dir.iterdir():
        if path.is_file():
            path.unlink()

    #print("All files deleted from ./data_up1")
    rss_files = download_rss(urls, "data_up1")

    Common_RSS = combine_rss_files(
        rss_files
            )

    
    rss_to_json(Common_RSS)

    for i in range(len(rss_files) - 1):
        for j in range(i + 1, len(rss_files)):
            #Generates OUTPUT_JSON
            processURLs(rss_files[i], rss_files[j])
    
    print("Starting  Ranking")
    
    processRanking(FINPUT_JSON,Common_Json)
    
    print("Ranking Finished")
    



if __name__ == "__main__":
    main()
