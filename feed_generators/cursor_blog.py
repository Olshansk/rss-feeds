import argparse
import re
from datetime import datetime

from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator

from utils import (
    deserialize_entries,
    fetch_page,
    load_cache,
    merge_entries,
    save_cache,
    save_rss_feed,
    setup_feed_links,
    setup_logging,
    sort_posts_for_feed,
)

logger = setup_logging()

BLOG_URL = "https://cursor.com/blog"
FEED_NAME = "cursor"


def parse_posts(html):
    """Extract posts from HTML. Returns (posts, next_page_url or None)."""
    soup = BeautifulSoup(html, "html.parser")
    posts = []

    for card in soup.find_all("a", class_=re.compile(r"card")):
        href = card.get("href", "")
        if "/blog/" not in href or "/topic/" in href or "/page/" in href:
            continue

        # Make URL absolute
        if href.startswith("/"):
            href = f"https://cursor.com{href}"

        ps = card.find_all("p")
        title = ps[0].get_text(strip=True) if ps else ""
        description = ps[1].get_text(strip=True) if len(ps) > 1 else ""

        time_el = card.find("time")
        date = time_el.get("datetime", "") if time_el else ""

        category_el = card.find("span", class_="capitalize")
        category = category_el.get_text(strip=True).rstrip(" ·") if category_el else ""

        posts.append(
            {
                "link": href,
                "title": title,
                "description": description,
                "date": date,
                "category": category,
            }
        )

    # Find next page link - look for links containing "Next" or "Older"
    next_link = None
    for link in soup.find_all("a", href=re.compile(r"/blog/page/\d+")):
        link_text = link.get_text(strip=True)
        if "Next" in link_text or "Older" in link_text:
            next_link = link
            break

    next_url = None
    if next_link:
        href = next_link.get("href")
        # Make relative URLs absolute
        if href.startswith("/"):
            next_url = f"https://cursor.com{href}"
        else:
            next_url = href

    return posts, next_url


def fetch_all_pages():
    """Follow pagination until no Next link. Returns all posts."""
    all_posts = []
    url = BLOG_URL
    page_num = 1

    while url:
        logger.info(f"Fetching page {page_num}: {url}")
        html = fetch_page(url)
        posts, next_url = parse_posts(html)
        all_posts.extend(posts)
        logger.info(f"Found {len(posts)} posts on page {page_num}")

        url = next_url
        page_num += 1

    # Dedupe by URL (in case of overlaps)
    seen = set()
    unique_posts = []
    for post in all_posts:
        if post["link"] not in seen:
            unique_posts.append(post)
            seen.add(post["link"])

    # Sort for correct feed order (newest first in output)
    sorted_posts = sort_posts_for_feed(unique_posts, date_field="date")
    logger.info(f"Total unique posts across all pages: {len(sorted_posts)}")
    return sorted_posts


def generate_rss_feed(posts):
    """Generate RSS feed from posts."""
    fg = FeedGenerator()
    fg.title("Cursor Blog")
    fg.description("The AI Code Editor")
    fg.language("en")
    fg.author({"name": "Cursor"})
    fg.logo("https://cursor.com/favicon.ico")
    fg.subtitle("Latest updates from Cursor")
    setup_feed_links(fg, blog_url=BLOG_URL, feed_name=FEED_NAME)

    for post in posts:
        fe = fg.add_entry()
        fe.title(post["title"])
        fe.description(post["description"])
        fe.link(href=post["link"])
        fe.id(post["link"])

        if post.get("date"):
            try:
                dt = datetime.fromisoformat(post["date"].replace("Z", "+00:00"))
                fe.published(dt)
            except ValueError:
                pass

        if post.get("category"):
            fe.category(term=post["category"])

    logger.info(f"Generated RSS feed with {len(posts)} entries")
    return fg


def main(full_reset=False):
    """Main function to generate RSS feed."""
    cache = load_cache(FEED_NAME)
    cached_entries = deserialize_entries(cache.get("entries", []))

    if full_reset or not cached_entries:
        mode = "full reset" if full_reset else "no cache exists"
        logger.info(f"Running full fetch ({mode})")
        posts = fetch_all_pages()
    else:
        logger.info("Running incremental update (page 1 only)")
        html = fetch_page(BLOG_URL)
        new_posts, _ = parse_posts(html)
        logger.info(f"Found {len(new_posts)} posts on page 1")
        posts = merge_entries(new_posts, cached_entries)

    save_cache(FEED_NAME, posts)
    feed = generate_rss_feed(posts)
    save_rss_feed(feed, FEED_NAME)

    logger.info("Done!")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Cursor Blog RSS feed")
    parser.add_argument("--full", action="store_true", help="Force full reset (fetch all pages)")
    args = parser.parse_args()
    main(full_reset=args.full)
