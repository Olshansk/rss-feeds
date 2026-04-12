import argparse
from datetime import datetime

import pytz
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator

from utils import (
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

BLOG_URL = "https://dagster.io/blog"
FEED_NAME = "dagster"
# Dagster uses Webflow CMS pagination with this query param
PAGINATION_PARAM = "a17fdf47_page"



def parse_posts(html_content):
    """Parse the blog HTML content and extract post information.

    Returns (posts, has_next_page).
    """
    soup = BeautifulSoup(html_content, "html.parser")
    blog_posts = []

    # Parse the featured blog post (if present)
    featured_post = soup.select_one("div.featured_blog_link")
    if featured_post:
        title_elem = featured_post.select_one("h2.heading-style-h5")
        date_elem = featured_post.select_one("p.text-color-neutral-500")
        description_elem = featured_post.select_one("p.text-color-neutral-700")
        link_elem = featured_post.select_one("a.clickable_link")

        if title_elem and date_elem and link_elem:
            title = title_elem.text.strip()
            date_str = date_elem.text.strip()
            date_obj = datetime.strptime(date_str, "%B %d, %Y")
            description = description_elem.text.strip() if description_elem else ""
            link = link_elem.get("href", "")

            if link.startswith("/"):
                link = f"https://dagster.io{link}"

            if link:
                blog_posts.append(
                    {
                        "link": link,
                        "title": title,
                        "date": date_obj.strftime("%Y-%m-%d"),
                        "description": description,
                    }
                )

    # Find all regular blog post cards
    posts = soup.select("div.blog_card")

    for post in posts:
        title_elem = post.select_one("h3.blog_card_title")
        if not title_elem:
            continue
        title = title_elem.text.strip()

        date_elem = post.select_one("p.text-color-neutral-500.text-size-small")
        if not date_elem:
            continue
        date_str = date_elem.text.strip()
        date_obj = datetime.strptime(date_str, "%B %d, %Y")

        description_elem = post.select_one('p[fs-cmsfilter-field="description"]')
        description = description_elem.text.strip() if description_elem else ""

        link_elem = post.select_one("a.clickable_link")
        if not link_elem or not link_elem.get("href"):
            continue
        link = link_elem["href"]

        if link.startswith("/"):
            link = f"https://dagster.io{link}"

        blog_posts.append(
            {
                "link": link,
                "title": title,
                "date": date_obj.strftime("%Y-%m-%d"),
                "description": description,
            }
        )

    # Check for "Load more" / next page link
    next_link = soup.select_one("a.w-pagination-next")
    has_next_page = next_link is not None and next_link.get("href")

    return blog_posts, has_next_page


def fetch_all_pages():
    """Follow pagination until no next link. Returns all posts."""
    all_posts = []
    page_num = 1

    while True:
        if page_num == 1:
            url = BLOG_URL
        else:
            url = f"{BLOG_URL}?{PAGINATION_PARAM}={page_num}"

        logger.info(f"Fetching page {page_num}: {url}")
        html = fetch_page(url)
        posts, has_next_page = parse_posts(html)
        all_posts.extend(posts)
        logger.info(f"Found {len(posts)} posts on page {page_num}")

        if not has_next_page:
            break
        page_num += 1

    # Dedupe by URL
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
    """Generate RSS feed from blog posts."""
    fg = FeedGenerator()
    fg.title("Dagster Blog")
    fg.description(
        "Read the latest from the Dagster team: insights, tutorials, and updates on data engineering, orchestration, and building better pipelines."
    )
    fg.language("en")

    fg.author({"name": "Dagster"})
    fg.subtitle("Latest updates from Dagster")
    setup_feed_links(fg, blog_url=BLOG_URL, feed_name=FEED_NAME)

    for post in posts:
        fe = fg.add_entry()
        fe.title(post["title"])
        fe.description(post["description"])
        fe.link(href=post["link"])
        fe.id(post["link"])

        if post.get("date"):
            try:
                dt = datetime.strptime(post["date"], "%Y-%m-%d")
                fe.published(dt.replace(tzinfo=pytz.UTC))
            except ValueError:
                pass

    logger.info(f"Generated RSS feed with {len(posts)} entries")
    return fg


def main(full_reset=False):
    """Main function to generate RSS feed from blog URL.

    Args:
        full_reset: If True, fetch all pages. If False, only fetch page 1
                   and merge with cached posts.
    """
    cache = load_cache(FEED_NAME)

    if full_reset or not cache.get("entries", []):
        mode = "full reset" if full_reset else "no cache exists"
        logger.info(f"Running full fetch ({mode})")
        posts = fetch_all_pages()
    else:
        logger.info("Running incremental update (page 1 only)")
        html = fetch_page(BLOG_URL)
        new_posts, _ = parse_posts(html)
        logger.info(f"Found {len(new_posts)} posts on page 1")
        posts = merge_entries(new_posts, cache["entries"])

    save_cache(FEED_NAME, posts)
    feed = generate_rss_feed(posts)
    save_rss_feed(feed, FEED_NAME)

    logger.info("Done!")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Dagster Blog RSS feed")
    parser.add_argument(
        "--full", action="store_true", help="Force full reset (fetch all pages)"
    )
    args = parser.parse_args()
    main(full_reset=args.full)
