from datetime import datetime

import pytz
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator

from utils import fetch_page, save_rss_feed, setup_feed_links, setup_logging, stable_fallback_date

logger = setup_logging()

FEED_NAME = "hamel"
BLOG_URL = "https://hamel.dev/"


def parse_blog_page(html_content, base_url="https://hamel.dev"):
    """Parse the blog HTML page and extract blog post information.

    Args:
        html_content: HTML content of the blog page
        base_url: Base URL for the website
    """
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        blog_posts = []

        # Find all blog post rows in the listing table
        rows = soup.select("#listing-blog-listings tbody tr")
        logger.info(f"Found {len(rows)} blog posts")

        for row in rows:
            try:
                # Extract date from the listing-date span
                date_span = row.select_one("span.listing-date")
                if not date_span:
                    continue
                date_text = date_span.get_text(strip=True)

                # Extract title and link from the anchor tag
                title_link = row.select_one("a.listing-title")
                if not title_link:
                    continue

                title = title_link.get_text(strip=True)
                href = title_link.get("href") or title_link.get("data-original-href")
                if not href:
                    continue

                # Make URL absolute if it's relative
                if href.startswith("/"):
                    full_url = f"{base_url}{href}"
                elif not href.startswith("http"):
                    full_url = f"{base_url}/{href}"
                else:
                    full_url = href

                # Parse the date (format: MM/DD/YY)
                try:
                    pub_date = datetime.strptime(date_text, "%m/%d/%y")
                    pub_date = pub_date.replace(tzinfo=pytz.UTC)
                except ValueError:
                    logger.warning(f"Could not parse date '{date_text}' for post '{title}'")
                    pub_date = stable_fallback_date(full_url)

                blog_post = {
                    "title": title,
                    "link": full_url,
                    "description": title,  # Use title as description since we don't fetch article content
                    "date": pub_date,
                }

                blog_posts.append(blog_post)
                logger.info(f"Parsed post: {title} ({date_text})")

            except Exception as e:
                logger.warning(f"Error parsing row: {e!s}")
                continue

        logger.info(f"Successfully parsed {len(blog_posts)} blog posts")
        return blog_posts

    except Exception as e:
        logger.error(f"Error parsing HTML content: {e!s}")
        raise


def generate_rss_feed(blog_posts):
    """Generate RSS feed from blog posts."""
    try:
        fg = FeedGenerator()
        fg.title("Hamel Husain's Blog")
        fg.description("Notes on applied AI engineering, machine learning, and data science.")
        fg.language("en")

        # Set feed metadata
        fg.author({"name": "Hamel Husain"})
        fg.subtitle("Applied AI engineering, machine learning, and data science")
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
        logger.error(f"Error generating RSS feed: {e!s}")
        raise


def main():
    """Main function to generate RSS feed from blog URL."""
    try:
        # Fetch blog content
        html_content = fetch_page(BLOG_URL)

        # Parse blog posts
        blog_posts = parse_blog_page(html_content)

        # Generate RSS feed
        feed = generate_rss_feed(blog_posts)

        # Save feed to file
        save_rss_feed(feed, FEED_NAME)

        return True

    except Exception as e:
        logger.error(f"Failed to generate RSS feed: {e!s}")
        return False


if __name__ == "__main__":
    main()
