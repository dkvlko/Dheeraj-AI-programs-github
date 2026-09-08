import feedparser
from jinja2 import Template
from dateutil import parser

rss_feeds = [
    ("ABP", "https://news.abplive.com/home/feed"),
    ("TimesOfIndia", "http://timesofindia.indiatimes.com/rssfeedstopstories.cms"),
    ("TheHindu", "https://www.thehindu.com/feeder/default.rss"),
]

template = Template("""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{{ feed.feed.title }}</title>
</head>
<body>

<h1>{{ feed.feed.title }}</h1>

{% for item in feed.entries %}
    <article>
        <h2>
            <a href="{{ item.link }}" target="_blank">
                {{ item.title }}
            </a>
        </h2>

        {% if item.get("published") %}
            <small>{{ item.published }}</small>
        {% endif %}

        {% if item.get("summary") %}
            <p>{{ item.summary }}</p>
        {% endif %}
    </article>
{% endfor %}

</body>
</html>
""")

for source, rss_url in rss_feeds:

    print(f"Fetching {source}...")

    feed = feedparser.parse(rss_url)

    # Sort news by publication date/time
    def get_date(item):
        try:
            if item.get("published"):
                return parser.parse(item.published)
            elif item.get("updated"):
                return parser.parse(item.updated)
        except Exception:
            pass

        # Put items without a valid date at the end
        return parser.parse("1970-01-01T00:00:00Z")

    feed.entries.sort(key=get_date, reverse=True)

    filename = f"news_{source}.html"

    html = template.render(feed=feed)

    with open(filename, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Created {filename}")
