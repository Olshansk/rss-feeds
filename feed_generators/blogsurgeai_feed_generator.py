#!/usr/bin/env python3
"""
RSS Feed Generator for Surge AI Blog
Scrapes https://www.surgehq.ai/blog and generates an RSS feed
"""

import pytz
from bs4 import BeautifulSoup
from dateutil import parser
from feedgen.feed import FeedGenerator

from utils import fetch_page, save_rss_feed, setup_feed_links, setup_logging, stable_fallback_date

logger = setup_logging()

FEED_NAME = "blogsurgeai"
BLOG_URL = "https://www.surgehq.ai/blog"


def generate_blogsurgeai_feed():
    """Generate RSS feed for Surge AI blog"""

    # Initialize feed generator
    fg = FeedGenerator()
    fg.id(BLOG_URL)
    fg.title("Surge AI Blog")
    fg.author({"name": "Surge AI", "email": "team@surgehq.ai"})
    setup_feed_links(fg, blog_url=BLOG_URL, feed_name=FEED_NAME)
    fg.language("en")
    fg.description(
        "New methods, current trends & software infrastructure for NLP. Articles written by our senior engineering leads from Google, Facebook, Twitter, Harvard, MIT, and Y Combinator"
    )

    # Fetch the blog page
    try:
        html = fetch_page(BLOG_URL)
    except Exception as e:
        logger.error(f"Error fetching blog page: {e}")
        return

    # Parse HTML
    soup = BeautifulSoup(html, "html.parser")

    # Find all blog post items
    blog_items = soup.find_all("div", class_="blog-hero-cms-item")

    logger.info(f"Found {len(blog_items)} blog posts")

    # Process each blog post
    for item in blog_items:
        try:
            # Find the title
            title_element = item.find("div", class_="blog-hero-cms-item-title")
            if not title_element:
                continue

            title = title_element.get_text(strip=True)

            # Find the link
            link_element = item.find("a", class_="blog-hero-cms-item-link")
            if not link_element:
                continue

            link = link_element.get("href")
            if not link.startswith("http"):
                link = "https://www.surgehq.ai" + link

            # Find the description
            desc_element = item.find("div", class_="blog-hero-cms-item-desc")
            description = desc_element.get_text(strip=True) if desc_element else title

            # Find the date
            date_element = item.find("div", class_="blog-hero-cms-item-date")
            pub_date = None  # Will be set by parsing or fallback

            if date_element:
                # Find the visible date element (the one without w-condition-invisible)
                date_texts = date_element.find_all("div", class_="txt fs-12 inline")
                for date_text in date_texts:
                    if "w-condition-invisible" not in date_text.get("class", []):
                        date_str = date_text.get_text(strip=True)
                        try:
                            # Parse the date string (e.g., "October 10, 2025")
                            pub_date = parser.parse(date_str)
                            # Make timezone-aware
                            if pub_date.tzinfo is None:
                                pub_date = pytz.UTC.localize(pub_date)
                            break
                        except Exception as e:
                            logger.warning(f"Could not parse date '{date_str}': {e}")

            # Use stable fallback if no date was parsed
            if pub_date is None:
                pub_date = stable_fallback_date(link)

            # Create feed entry
            fe = fg.add_entry()
            fe.id(link)
            fe.title(title)
            fe.link(href=link)
            fe.published(pub_date)

            # Set description
            fe.description(description)

            logger.info(f"Added: {title}")

        except Exception as e:
            logger.error(f"Error processing blog item: {e}")
            continue

    # Generate RSS feed
    save_rss_feed(fg, FEED_NAME)


if __name__ == "__main__":
    generate_blogsurgeai_feed()
