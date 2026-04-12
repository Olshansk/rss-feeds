from datetime import datetime

import pytz
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator

from utils import (
    fetch_page,
    save_rss_feed,
    setup_feed_links,
    setup_logging,
    sort_posts_for_feed,
    stable_fallback_date,
)

logger = setup_logging()

FEED_NAME = "chanderramesh"
BLOG_URL = "https://chanderramesh.com/writing"


def parse_date(date_str):
    """Parse date string in format 'Month DD, YYYY'."""
    try:
        # Parse date like "June 12, 2025" or "February 8, 2025"
        date = datetime.strptime(date_str.strip(), "%B %d, %Y")
        return date.replace(tzinfo=pytz.UTC)
    except ValueError as e:
        logger.warning(f"Could not parse date: {date_str} - {str(e)}")
        return None


def parse_writing_page(html_content, base_url="https://chanderramesh.com"):
    """Parse the writing page and extract blog post information."""
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        blog_posts = []

        # Find all essay cards - they are links with classes "group" and "masonry-item"
        # Note: class_ parameter must be a list when searching for multiple classes
        essay_links = soup.find_all("a", class_=["group", "masonry-item"])
        logger.info(f"Found {len(essay_links)} essays")

        for link in essay_links:
            # Extract the URL
            href = link.get("href")
            if not href:
                continue

            full_url = f"{base_url}{href}" if href.startswith("/") else href

            # Extract date
            date_elem = link.find("p", class_="text-muted-foreground mb-2 text-sm")
            date_str = date_elem.get_text(strip=True) if date_elem else None

            # Extract title
            title_elem = link.find(
                "h3", class_="font-semibold tracking-tight mb-3 text-xl font-serif"
            )
            title = title_elem.get_text(strip=True) if title_elem else "Untitled"

            # Extract description
            desc_elem = link.find("p", class_="leading-relaxed text-muted-foreground")
            description = desc_elem.get_text(strip=True) if desc_elem else ""

            # Parse date
            pub_date = (
                parse_date(date_str) if date_str else None
            ) or stable_fallback_date(full_url)

            blog_post = {
                "title": title,
                "link": full_url,
                "description": description,
                "date": pub_date,
            }

            blog_posts.append(blog_post)
            logger.info(f"Parsed: {title} ({date_str})")

        # Sort for correct feed order (newest first in output)
        blog_posts = sort_posts_for_feed(blog_posts)

        logger.info(f"Successfully parsed {len(blog_posts)} blog posts")
        return blog_posts

    except Exception as e:
        logger.error(f"Error parsing HTML content: {str(e)}")
        raise


def generate_rss_feed(blog_posts):
    """Generate RSS feed from blog posts."""
    try:
        fg = FeedGenerator()
        fg.title("Chander Ramesh - Writing")
        fg.description(
            "Essays by Chander Ramesh covering software, startups, investing, and philosophy"
        )
        fg.language("en")

        # Set feed metadata
        fg.author({"name": "Chander Ramesh"})
        fg.subtitle("Essays covering software, startups, investing, and philosophy")
        setup_feed_links(fg, blog_url=BLOG_URL, feed_name=FEED_NAME)

        # Add entries
        for post in blog_posts:
            fe = fg.add_entry()
            fe.title(post["title"])
            fe.description(post["description"])
            fe.link(href=post["link"])
            fe.published(post["date"])
            fe.id(post["link"])

        logger.info("Successfully generated RSS feed")
        return fg

    except Exception as e:
        logger.error(f"Error generating RSS feed: {str(e)}")
        raise


def main():
    """Main function to generate RSS feed from blog URL."""
    try:
        # Fetch blog content
        html_content = fetch_page(BLOG_URL)

        # Parse blog posts
        blog_posts = parse_writing_page(html_content)

        # Generate RSS feed
        feed = generate_rss_feed(blog_posts)

        # Save feed to file
        save_rss_feed(feed, FEED_NAME)

        return True

    except Exception as e:
        logger.error(f"Failed to generate RSS feed: {str(e)}")
        return False


if __name__ == "__main__":
    main()
