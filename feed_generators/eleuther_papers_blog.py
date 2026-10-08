"""Generate an RSS feed for EleutherAI's papers listing.

https://www.eleuther.ai/papers

Static research-library cards provide titles, authors, links and years.
arXiv supplies original publication dates where available.
"""

import argparse

from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator

from feed_history import load_feed_history, merge_feed_history
from paper_dates import enrich_paper_dates
from utils import (
    fetch_page,
    save_rss_feed,
    setup_feed_links,
    setup_logging,
    sort_posts_for_feed,
)

logger = setup_logging()

FEED_NAME = "eleuther_papers"
BLOG_URL = "https://www.eleuther.ai/papers"
FEED_TITLE = "EleutherAI Papers"
FEED_DESCRIPTION = "Papers and preprints from EleutherAI"
AUTHOR = "EleutherAI"


def parse(html_content):
    """Read the research library's semantic fields; enrich dates separately."""
    posts = {}
    soup = BeautifulSoup(html_content, "html.parser")
    for card in soup.select("a.library-entry[href]"):
        title = card.find("h3")
        if title is None or not card.get("data-year"):
            raise ValueError("Research library card lacks title or publication year")
        link = card["href"]
        authors = card.select_one(".library-entry-authors")
        posts[link] = {
            "title": title.get_text(" ", strip=True),
            "link": link,
            "year": int(card["data-year"]),
            "date": None,
            "description": authors.get_text(" ", strip=True) if authors else title.get_text(),
        }
    return list(posts.values())


def generate_rss_feed(articles):
    fg = FeedGenerator()
    fg.title(FEED_TITLE)
    fg.description(FEED_DESCRIPTION)
    fg.language("en")
    fg.author({"name": AUTHOR})
    setup_feed_links(fg, blog_url=BLOG_URL, feed_name=FEED_NAME)

    for post in sort_posts_for_feed(articles):
        fe = fg.add_entry()
        fe.title(post["title"])
        fe.description(post.get("description") or post["title"])
        fe.link(href=post["link"])
        fe.published(post["date"])
        fe.id(post.get("guid") or post["link"])

    return fg


def main():
    parser = argparse.ArgumentParser(description=f"Generate the {FEED_TITLE} RSS feed")
    parser.add_argument("html_file", nargs="?", help="Optional local HTML file to parse instead of fetching")
    args = parser.parse_args()

    try:
        if args.html_file:
            logger.info(f"Reading local HTML file: {args.html_file}")
            with open(args.html_file, encoding="utf-8") as f:
                html_content = f.read()
        else:
            html_content = fetch_page(BLOG_URL)

        articles = parse(html_content)

        if not articles:
            logger.warning("No articles found - skipping feed update to avoid overwriting with empty feed")
            return False

        articles = enrich_paper_dates(articles, known_posts=load_feed_history(FEED_NAME))
        articles = merge_feed_history(articles, FEED_NAME)
        fg = generate_rss_feed(articles)
        save_rss_feed(fg, FEED_NAME)
        logger.info(f"Generated {FEED_NAME} feed with {len(articles)} articles")
        return True

    except Exception as e:
        logger.error(f"Failed to generate {FEED_NAME} feed: {e!s}")
        return False


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
