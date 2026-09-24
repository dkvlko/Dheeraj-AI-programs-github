#!/usr/bin/env python3.14

"""
Indian Express -> RSS 2.0 generator

Input:
    https://indianexpress.com/

Output:
    indianexpress.rss

The RSS file is written into the same directory as this script.

Python:
    3.14+

Dependencies:
    requests
    beautifulsoup4
"""

from __future__ import annotations

import html
import json
import re
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone,timedelta
from zoneinfo import ZoneInfo
from email.utils import format_datetime

from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

IST = ZoneInfo("Asia/Kolkata")
# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------

BASE_URL = "https://indianexpress.com/"
OUTPUT_FILE = Path(__file__).resolve().parent / "data" / "indianexpress.rss"

MAX_ITEMS = 100

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/140.0 Safari/537.36 "
    "IndianExpressRSS/1.0"
)

REQUEST_TIMEOUT = 30


# ----------------------------------------------------------------------
# Data structure
# ----------------------------------------------------------------------

@dataclass
class Article:
    title: str
    link: str
    description: str = ""
    category: str = ""
    author: str = ""
    published: str = ""
    updated: str = ""
    image: str = ""
    guid: str = ""


# ----------------------------------------------------------------------
# HTTP
# ----------------------------------------------------------------------

def download_homepage() -> str:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": (
            "text/html,application/xhtml+xml,"
            "application/xml;q=0.9,*/*;q=0.8"
        ),
        "Accept-Language": "en-IN,en;q=0.9",
        "Cache-Control": "no-cache",
    }

    response = requests.get(
        BASE_URL,
        headers=headers,
        timeout=REQUEST_TIMEOUT,
    )

    response.raise_for_status()

    response.encoding = response.apparent_encoding or response.encoding

    return response.text


def get_article_datetime(url: str) -> tuple[str, str]:
    """
    Fetch an Indian Express article and extract its real
    publication/update timestamps.

    Returns:
        (published, updated)

    Both are ISO-8601 strings containing +05:30.
    """

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-IN,en;q=0.9",
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )

        response.raise_for_status()

    except requests.RequestException:
        return "", ""

    soup = BeautifulSoup(
        response.text,
        "html.parser",
    )

    published = ""
    updated = ""

    # ----------------------------------------------------------
    # First choice: JSON-LD
    # ----------------------------------------------------------

    for script in soup.find_all(
        "script",
        attrs={"type": "application/ld+json"},
    ):

        if not script.string:
            continue

        try:
            data = json.loads(script.string)
        except (json.JSONDecodeError, TypeError):
            continue

        objects = []

        if isinstance(data, dict):
            objects.append(data)

            if isinstance(data.get("@graph"), list):
                objects.extend(data["@graph"])

        elif isinstance(data, list):
            objects.extend(data)

        for obj in objects:

            if not isinstance(obj, dict):
                continue

            published = first_nonempty(
                published,
                obj.get("datePublished"),
            )

            updated = first_nonempty(
                updated,
                obj.get("dateModified"),
            )

    # ----------------------------------------------------------
    # Second choice: visible article metadata
    # ----------------------------------------------------------

    page_text = soup.get_text(
        " ",
        strip=True,
    )

    # Example:
    #
    # First published on: Mar 20, 2017 at 01:31 PM IST
    #
    match = re.search(
        r"First published on:\s*"
        r"([A-Za-z]{3,9}\s+\d{1,2},\s+\d{4})"
        r"\s+at\s+"
        r"(\d{1,2}:\d{2}\s+[AP]M)\s+IST",
        page_text,
        re.I,
    )

    if match:
        date_part = match.group(1)
        time_part = match.group(2)

        try:
            dt = datetime.strptime(
                f"{date_part} {time_part}",
                "%b %d, %Y %I:%M %p",
            )

            dt = dt.replace(
                tzinfo=IST
            )

            published = dt.isoformat()

        except ValueError:

            try:
                dt = datetime.strptime(
                    f"{date_part} {time_part}",
                    "%B %d, %Y %I:%M %p",
                )

                dt = dt.replace(
                    tzinfo=IST
                )

                published = dt.isoformat()

            except ValueError:
                pass

    # ----------------------------------------------------------
    # Updated timestamp
    # ----------------------------------------------------------

    match = re.search(
        r"(?:Updated|Updated on):\s*"
        r"([A-Za-z]{3,9}\s+\d{1,2},\s+\d{4})"
        r"\s+at\s+"
        r"(\d{1,2}:\d{2}\s+[AP]M)\s+IST",
        page_text,
        re.I,
    )

    if match:
        date_part = match.group(1)
        time_part = match.group(2)

        for fmt in (
            "%b %d, %Y %I:%M %p",
            "%B %d, %Y %I:%M %p",
        ):
            try:
                dt = datetime.strptime(
                    f"{date_part} {time_part}",
                    fmt,
                )

                dt = dt.replace(
                    tzinfo=IST
                )

                updated = dt.isoformat()
                break

            except ValueError:
                continue

    return published, updated

# ----------------------------------------------------------------------
# Utility functions
# ----------------------------------------------------------------------

def clean_text(value: str | None) -> str:
    if not value:
        return ""

    value = html.unescape(value)

    value = re.sub(r"\s+", " ", value)

    return value.strip()


def absolute_url(url: str | None) -> str:
    if not url:
        return ""

    return urljoin(BASE_URL, url.strip())


def valid_article_url(url: str) -> bool:
    if not url:
        return False

    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        return False

    hostname = (parsed.hostname or "").lower()

    if hostname not in {
        "indianexpress.com",
        "www.indianexpress.com",
    }:
        return False

    # Avoid obvious non-article/navigation links.
    bad_parts = (
        "/author/",
        "/category/",
        "/page/",
        "/tag/",
        "/search/",
        "/wp-content/",
        "/subscribe/",
        "/login/",
    )

    path = parsed.path.lower()

    if any(part in path for part in bad_parts):
        return False

    return True


def first_nonempty(*values: str | None) -> str:
    for value in values:
        value = clean_text(value)

        if value:
            return value

    return ""


def meta_content(
    soup: BeautifulSoup,
    *,
    name: str | None = None,
    prop: str | None = None,
) -> str:
    tag = None

    if name:
        tag = soup.find(
            "meta",
            attrs={"name": name},
        )

    if not tag and prop:
        tag = soup.find(
            "meta",
            attrs={"property": prop},
        )

    if not tag:
        return ""

    return clean_text(tag.get("content", ""))


def get_image_from_tag(tag) -> str:
    if not tag:
        return ""

    # Normal image.
    for attr in ("src", "data-src", "data-lazy-src"):
        value = tag.get(attr)

        if value:
            return absolute_url(value)

    # Responsive image.
    srcset = tag.get("srcset") or tag.get("data-srcset")

    if srcset:
        first = srcset.split(",")[0].strip()

        if first:
            value = first.split()[0]
            return absolute_url(value)

    return ""


# ----------------------------------------------------------------------
# Article extraction
# ----------------------------------------------------------------------

def extract_title_from_link(link_tag) -> str:
    """
    Try several common title locations.
    """

    # Explicit title attributes.
    title = first_nonempty(
        link_tag.get("title"),
        link_tag.get("aria-label"),
    )

    if title:
        return title

    # Headings inside the link.
    heading = link_tag.find(
        ["h1", "h2", "h3", "h4", "h5", "h6"]
    )

    if heading:
        title = clean_text(heading.get_text(" ", strip=True))

        if title:
            return title

    # Image alt text is only a fallback.
    image = link_tag.find("img")

    if image:
        title = clean_text(image.get("alt"))

        if title:
            return title

    # Finally use visible text.
    title = clean_text(
        link_tag.get_text(" ", strip=True)
    )

    return title


def extract_article_from_container(
    container,
    fallback_link=None,
) -> Article | None:

    # --------------------------------------------------------------
    # Find URL
    # --------------------------------------------------------------

    link_tag = None

    if fallback_link:
        link_tag = fallback_link
    else:
        link_tag = container.find(
            "a",
            href=True,
        )

    if not link_tag:
        return None

    link = absolute_url(link_tag.get("href"))

    if not valid_article_url(link):
        return None

    # --------------------------------------------------------------
    # Title
    # --------------------------------------------------------------

    title = extract_title_from_link(link_tag)

    if not title:
        heading = container.find(
            ["h1", "h2", "h3", "h4", "h5"]
        )

        if heading:
            title = clean_text(
                heading.get_text(" ", strip=True)
            )

    if not title:
        return None

    # Avoid obvious navigation text.
    if len(title) < 5:
        return None

    # --------------------------------------------------------------
    # Description
    # --------------------------------------------------------------

    description = ""

    for selector in [
        "p",
        ".description",
        ".story__description",
        ".content",
        ".excerpt",
        ".summary",
    ]:
        element = container.select_one(selector)

        if element:
            text = clean_text(
                element.get_text(" ", strip=True)
            )

            if text and text != title:
                description = text
                break

    # --------------------------------------------------------------
    # Category
    # --------------------------------------------------------------

    category = ""

    for selector in [
        ".cat",
        ".category",
        ".story-category",
        ".article-category",
        "[class*='category']",
    ]:
        element = container.select_one(selector)

        if element:
            category = clean_text(
                element.get_text(" ", strip=True)
            )

            if category:
                break

    # --------------------------------------------------------------
    # Author
    # --------------------------------------------------------------

    author = ""

    for selector in [
        ".author",
        ".byline",
        ".story-author",
        ".article-author",
        "[class*='author']",
    ]:
        element = container.select_one(selector)

        if element:
            author = clean_text(
                element.get_text(" ", strip=True)
            )

            if author:
                break

    # --------------------------------------------------------------
    # Date
    # --------------------------------------------------------------

    published = ""

    time_tag = container.find("time")

    if time_tag:
        published = first_nonempty(
            time_tag.get("datetime"),
            time_tag.get_text(" ", strip=True),
        )

    if not published:
        published = first_nonempty(
            container.get("data-published"),
            container.get("data-date"),
        )

    # --------------------------------------------------------------
    # Image
    # --------------------------------------------------------------

    image = get_image_from_tag(
        container.find("img")
    )

    return Article(
        title=title,
        link=link,
        description=description,
        category=category,
        author=author,
        published=published,
        image=image,
        guid=link,
    )


# ----------------------------------------------------------------------
# JSON-LD extraction
# ----------------------------------------------------------------------

def extract_jsonld_articles(
    soup: BeautifulSoup,
) -> list[Article]:

    articles: list[Article] = []

    scripts = soup.find_all(
        "script",
        attrs={"type": "application/ld+json"},
    )

    def process_object(obj):

        if isinstance(obj, list):
            for item in obj:
                process_object(item)

            return

        if not isinstance(obj, dict):
            return

        # Some sites use @graph.
        graph = obj.get("@graph")

        if isinstance(graph, list):
            for item in graph:
                process_object(item)

        obj_type = obj.get("@type", "")

        if isinstance(obj_type, list):
            types = obj_type
        else:
            types = [obj_type]

        types = {
            str(x).lower()
            for x in types
        }

        if not (
            {"newsarticle", "article", "reportage"}
            & types
        ):
            return

        title = first_nonempty(
            obj.get("headline"),
            obj.get("name"),
        )

        url = absolute_url(
            obj.get("url")
        )

        if not title or not valid_article_url(url):
            return

        description = first_nonempty(
            obj.get("description"),
        )

        author = ""

        author_obj = obj.get("author")

        if isinstance(author_obj, dict):
            author = first_nonempty(
                author_obj.get("name")
            )

        elif isinstance(author_obj, list):
            names = []

            for item in author_obj:
                if isinstance(item, dict):
                    name = clean_text(
                        item.get("name")
                    )

                    if name:
                        names.append(name)

                elif isinstance(item, str):
                    names.append(
                        clean_text(item)
                    )

            author = ", ".join(
                dict.fromkeys(names)
            )

        elif isinstance(author_obj, str):
            author = clean_text(author_obj)

        image = ""

        image_obj = obj.get("image")

        if isinstance(image_obj, str):
            image = absolute_url(image_obj)

        elif isinstance(image_obj, dict):
            image = absolute_url(
                image_obj.get("url")
            )

        elif isinstance(image_obj, list):
            for item in image_obj:
                if isinstance(item, str):
                    image = absolute_url(item)
                    break

                if isinstance(item, dict):
                    image = absolute_url(
                        item.get("url")
                    )

                    if image:
                        break

        article = Article(
            title=title,
            link=url,
            description=description,
            author=author,
            published=first_nonempty(
                obj.get("datePublished")
            ),
            updated=first_nonempty(
                obj.get("dateModified")
            ),
            image=image,
            guid=url,
        )

        articles.append(article)

    for script in scripts:

        raw = script.string

        if not raw:
            continue

        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue

        process_object(data)

    return articles


# ----------------------------------------------------------------------
# Main HTML extraction
# ----------------------------------------------------------------------

def extract_articles(html_text: str) -> list[Article]:

    soup = BeautifulSoup(
        html_text,
        "html.parser",
    )

    articles: list[Article] = []

    # --------------------------------------------------------------
    # 1. JSON-LD is usually the cleanest source.
    # --------------------------------------------------------------

    articles.extend(
        extract_jsonld_articles(soup)
    )

    # --------------------------------------------------------------
    # 2. Look specifically in Latest News.
    # --------------------------------------------------------------

    latest_heading = None

    for heading in soup.find_all(
        ["h1", "h2", "h3", "h4"]
    ):

        text = clean_text(
            heading.get_text(" ", strip=True)
        ).lower()

        if text in {
            "latest news",
            "latest",
        }:

            latest_heading = heading
            break

    if latest_heading:

        # Search nearby elements.
        parent = latest_heading.parent

        if parent:
            for link in parent.find_all(
                "a",
                href=True,
            ):

                article = extract_article_from_container(
                    link,
                    fallback_link=link,
                )

                if article:
                    articles.append(article)

    # --------------------------------------------------------------
    # 3. General fallback: inspect all links.
    # --------------------------------------------------------------

    for link in soup.find_all(
        "a",
        href=True,
    ):

        url = absolute_url(
            link.get("href")
        )

        if not valid_article_url(url):
            continue

        # Ignore anchors without meaningful text.
        title = extract_title_from_link(link)

        if not title or len(title) < 10:
            continue

        # Use the surrounding article/card when possible.
        container = (
            link.find_parent("article")
            or link.find_parent(
                class_=re.compile(
                    r"(story|article|post|news|card)",
                    re.I,
                )
            )
            or link.parent
        )

        article = extract_article_from_container(
            container,
            fallback_link=link,
        )

        if article:
            articles.append(article)

    # --------------------------------------------------------------
    # Deduplicate.
    # --------------------------------------------------------------

    unique: dict[str, Article] = {}

    for article in articles:

        # Normalize URL by removing fragments.
        parsed = urlparse(article.link)

        normalized = parsed._replace(
            fragment=""
        ).geturl()

        article.link = normalized
        article.guid = normalized

        if normalized not in unique:
            unique[normalized] = article
        else:
            # Merge missing information from the
            # later extraction method.
            old = unique[normalized]

            if not old.description:
                old.description = article.description

            if not old.category:
                old.category = article.category

            if not old.author:
                old.author = article.author

            if not old.published:
                old.published = article.published

            if not old.updated:
                old.updated = article.updated

            if not old.image:
                old.image = article.image

    return list(unique.values())


# ----------------------------------------------------------------------
# XML helpers
# ----------------------------------------------------------------------

def xml_escape(value: str) -> str:
    return html.escape(
        value or "",
        quote=True,
    )


def parse_date(value: str) -> datetime | None:

    if not value:
        return None

    value = value.strip()

    # ISO format.
    try:
        value2 = value.replace(
            "Z",
            "+00:00",
        )

        dt = datetime.fromisoformat(value2)

        if dt.tzinfo is None:
            dt = dt.replace(
                tzinfo=timezone.utc
            )

        return dt

    except ValueError:
        pass

    # Common Indian Express-style dates.
    formats = [
        "%B %d, %Y",
        "%b %d, %Y",
        "%d %B %Y",
        "%d %b %Y",
        "%Y-%m-%d %H:%M:%S",
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(
                value,
                fmt,
            )

            return dt.replace(
                tzinfo=timezone.utc
            )

        except ValueError:
            continue

    return None


def rss_date(article: Article) -> str:

    # Prefer the ORIGINAL publication time.
    # Do not use updated time here because this field is pubDate.
    dt = (
        parse_date(article.published)
        or parse_date(article.updated)
    )

    if dt:
        # Convert explicitly to Indian Standard Time.
        dt = dt.astimezone(IST)

        # usegmt=False produces +0530 instead of GMT.
        return format_datetime(
            dt,
            usegmt=False,
        )

    # Final fallback: current time in IST.
    return format_datetime(
        datetime.now(IST),
        usegmt=False,
    )

# ----------------------------------------------------------------------
# RSS generator
# ----------------------------------------------------------------------

def make_rss(articles: list[Article]) -> str:

    now = datetime.now(IST)

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0"',
        '     xmlns:content="http://purl.org/rss/1.0/modules/content/"',
        '     xmlns:media="http://search.yahoo.com/mrss/">',
        "  <channel>",
        "    <title>The Indian Express - Latest News</title>",
        f"    <link>{xml_escape(BASE_URL)}</link>",
        "    <description>Latest news from The Indian Express</description>",
        "    <language>en-IN</language>",
        f"    <lastBuildDate>{format_datetime(now, usegmt=False)}</lastBuildDate>",
        f"    <generator>Indian Express Python 3.14 RSS Generator</generator>",
        "",
    ]

    for article in articles[:MAX_ITEMS]:

        description = article.description

        # If no summary was found, use the title.
        if not description:
            description = article.title

        # Add metadata to the RSS description.
        extra = []

        if article.category:
            extra.append(
                f"Category: {article.category}"
            )

        if article.author:
            extra.append(
                f"Author: {article.author}"
            )

        if extra:
            description += "\n\n" + " | ".join(extra)

        lines.extend(
            [
                "    <item>",
                f"      <title>{xml_escape(article.title)}</title>",
                f"      <link>{xml_escape(article.link)}</link>",
                f"      <guid isPermaLink=\"true\">{xml_escape(article.guid)}</guid>",
                f"      <description>{xml_escape(description)}</description>",
                f"      <pubDate>{xml_escape(rss_date(article))}</pubDate>",
            ]
        )

        if article.category:
            lines.append(
                f"      <category>{xml_escape(article.category)}</category>"
            )

        if article.author:
            lines.append(
                f"      <dc:creator>{xml_escape(article.author)}</dc:creator>"
            )

        if article.image:
            lines.append(
                f'      <media:content url="{xml_escape(article.image)}" medium="image" />'
            )

        lines.extend(
            [
                "    </item>",
                "",
            ]
        )

    lines.extend(
        [
            "  </channel>",
            "</rss>",
            "",
        ]
    )

    # dc:creator requires this namespace.
    rss = "\n".join(lines)

    rss = rss.replace(
        'xmlns:media="http://search.yahoo.com/mrss/">',
        'xmlns:media="http://search.yahoo.com/mrss/" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/">',
    )

    return rss


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------

def generate_rss() -> int:

    #print(
    #    f"Downloading: {BASE_URL}"
    #)

    try:
        html_text = download_homepage()

    except requests.RequestException as exc:
        print(
            f"ERROR: Could not download website: {exc}",
            file=sys.stderr,
        )

        return 1

    #print(
    #    f"Downloaded {len(html_text):,} bytes"
    #)

    articles = extract_articles(
        html_text
    )

    # Remove articles without a usable title.
    articles = [
        article
        for article in articles
        if article.title
        and article.link
        and len(article.title.strip()) >= 40
    ]

    #print(
    #    f"Fetching real publication times for {len(articles)} articles..."
    #)

    for number, article in enumerate(
        articles,
        start=1,
    ):

        #print(
        #    f"[{number}/{len(articles)}] "
        #    f"{article.title[:70]}"
        #)

        published, updated = get_article_datetime(
            article.link
        )

        if published:
            article.published = published

        if updated:
            article.updated = updated
            
# ------------------------------------------------------------------
# Keep only articles published within the last 24 hours (IST)
# ------------------------------------------------------------------

    cutoff_time = datetime.now(IST) - timedelta(hours=12)

    articles = [
        article
        for article in articles
        if (
            parse_date(article.published)
            and parse_date(article.published).astimezone(IST)
            >= cutoff_time
        )
    ]
    #print(
    #    f"Articles published within the last 24 hours: {len(articles)}"
    #)
    # Prefer articles that have dates.
    articles.sort(
        key=lambda article: (
            parse_date(article.updated)
            or parse_date(article.published)
            or datetime.min.replace(
                tzinfo=timezone.utc
            )
        ),
        reverse=True,
    )

    rss = make_rss(
        articles
    )

    OUTPUT_FILE.write_text(
        rss,
        encoding="utf-8",
    )

    #print(
    #    f"Extracted {len(articles)} unique articles"
    #)

    #print(
    #    f"RSS written to:\n{OUTPUT_FILE}"
    #)

    #print("\nFirst 10 articles:")

    for number, article in enumerate(
        articles[:10],
        start=1,
    ):
        #print(
        #    f"{number:2}. {article.title}"
        #)

    return 0


def main() -> int:
    generate_rss()

if __name__ == "__main__":
    raise SystemExit(
        main()
    )
