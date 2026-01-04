import logging
import re
from datetime import datetime
from pathlib import Path

import pytz
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
from feedgen.feed import FeedGenerator

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


PROJECT_ROOT = Path(__file__).parent.parent
HTML_FILENAME = "The Batch _ DeepLearning.AI _ AI News & Insights.html"
BLOG_URL = "https://www.deeplearning.ai/the-batch/"


def ensure_feeds_directory() -> Path:
    feeds_dir = PROJECT_ROOT / "feeds"
    feeds_dir.mkdir(exist_ok=True)
    return feeds_dir


def parse_date(value: str | None) -> datetime:
    """Parse date text/datetime strings into timezone-aware datetime."""
    if not value:
        return datetime.now(tz=pytz.UTC)
    try:
        dt = date_parser.parse(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=pytz.UTC)
        return dt
    except (ValueError, TypeError) as exc:
        logger.warning("Unable to parse date %r (%s); using current time", value, exc)
        return datetime.now(tz=pytz.UTC)


def clean_text(text: str | None) -> str | None:
    if text is None:
        return None
    return " ".join(text.split())


def extract_article_link(article) -> str | None:
    """Return first deeplearning.ai article link excluding tag links."""
    for anchor in article.find_all("a", href=True):
        href = anchor["href"]
        if "deeplearning.ai/the-batch" not in href:
            continue
        if "/tag/" in href:
            continue
        return href
    return None


def extract_date_text(article) -> str | None:
    time_el = article.find("time")
    if time_el:
        return time_el.get("datetime") or time_el.get_text(" ", strip=True)

    # Featured card uses a pill with plain text (e.g., "Dec 26, 2025")
    date_pattern = re.compile(
        "(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\\s+\\d{1,2},\\s+\\d{4}",
        re.I,
    )
    for tag in article.find_all(["a", "div", "span"]):
        text = tag.get_text(" ", strip=True)
        match = date_pattern.search(text or "")
        if match:
            return match.group(0)
    return None


def extract_description(article) -> str | None:
    # Prefer visible snippet if present (line clamp text)
    summary = article.find(
        lambda tag: tag.name in {"div", "p"} and tag.get("class") and any("line-clamp" in cls for cls in tag.get("class"))
    )
    if summary:
        return clean_text(summary.get_text(" ", strip=True))

    first_para = article.find("p")
    if first_para:
        return clean_text(first_para.get_text(" ", strip=True))

    return None


def parse_articles_from_html(html_path: Path) -> list[dict]:
    soup = BeautifulSoup(html_path.read_text(), "lxml")
    articles = []

    for article in soup.find_all("article"):
        heading = article.find(["h1", "h2", "h3", "h4"])
        if not heading:
            continue

        title = clean_text(heading.get_text(" ", strip=True))
        link = extract_article_link(article)
        if not title or not link:
            continue

        date_text = extract_date_text(article)
        published = parse_date(date_text)
        description = extract_description(article) or title

        articles.append({"title": title, "link": link, "published": published, "description": description})

    logger.info("Parsed %d articles from %s", len(articles), html_path)
    return articles


def build_feed(articles: list[dict]) -> FeedGenerator:
    fg = FeedGenerator()
    fg.title("The Batch | DeepLearning.AI")
    fg.link(href=BLOG_URL, rel="alternate")
    fg.link(href=f"{BLOG_URL}feed_the_batch.xml", rel="self")
    fg.description("Weekly AI news and insights from DeepLearning.AI's The Batch.")
    fg.language("en")

    for article in sorted(articles, key=lambda a: a["published"], reverse=True):
        entry = fg.add_entry()
        entry.title(article["title"])
        entry.link(href=article["link"])
        entry.id(article["link"])
        entry.published(article["published"])
        entry.description(article["description"])

    return fg


def save_feed(feed: FeedGenerator, feed_name: str = "the_batch") -> Path:
    output_path = ensure_feeds_directory() / f"feed_{feed_name}.xml"
    feed.rss_file(str(output_path), pretty=True)
    logger.info("Wrote feed to %s", output_path)
    return output_path


def main():
    html_path = PROJECT_ROOT / HTML_FILENAME
    if not html_path.exists():
        raise FileNotFoundError(f"HTML file not found: {html_path}")

    articles = parse_articles_from_html(html_path)
    feed = build_feed(articles)
    save_feed(feed, "the_batch")


if __name__ == "__main__":
    main()
