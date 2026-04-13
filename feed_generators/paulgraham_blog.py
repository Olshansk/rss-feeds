import re
from datetime import datetime

import pytz
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator

from utils import fetch_page, save_rss_feed, setup_feed_links, setup_logging, stable_fallback_date

logger = setup_logging()

FEED_NAME = "paulgraham"
BLOG_URL = "https://paulgraham.com/articles.html"


def extract_date_from_text(text):
    """Helper function to extract date from text."""
    months = [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ]

    # Match "Month YYYY" pattern
    for month in months:
        pattern = f"{month}\\s+\\d{{4}}"
        match = re.search(pattern, text)
        if match:
            date_str = match.group(0)
            try:
                date = datetime.strptime(f"{date_str} 1", "%B %Y %d")
                return date.replace(tzinfo=pytz.UTC)
            except ValueError:
                continue
    return None


def get_article_content(article_html):
    """Extract the full article content and date."""
    try:
        soup = BeautifulSoup(article_html, "html.parser")
        content = None
        pub_date = None

        # Find the main content
        fonts = soup.find_all("font", size="2")
        for font in fonts:
            text = font.get_text().strip()
            if len(text) > 100:  # Main content is usually the longest text block
                content = text
                pub_date = extract_date_from_text(text)
                if pub_date:
                    # Remove the date from the beginning of the content
                    content = re.sub(r"^[A-Za-z]+ \d{4}", "", content).lstrip()
                break

        return content, pub_date

    except Exception as e:
        logger.error(f"Error extracting content: {e!s}")
        return None, None


def parse_essays_page(html_content, base_url="https://paulgraham.com", max_essays=300):
    """Parse the essays HTML page and extract blog post information.

    Args:
        html_content: HTML content of the essays page
        base_url: Base URL for the website
        max_essays: Maximum number of recent essays to fetch (default: 300)
    """
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        blog_posts = []

        # Find all essay links
        links = soup.select('font[size="2"] a')
        logger.info(f"Found {len(links)} total essays, will fetch up to {max_essays} most recent")

        # Limit to first N essays (they're listed in reverse chronological order)
        links_to_process = links[:max_essays]

        for link in links_to_process:
            # Extract title and link
            title = link.text.strip()
            href = link.get("href")
            if not href:
                continue

            full_url = f"{base_url}/{href}" if not href.startswith("http") else href

            logger.info(f"Fetching article: {title}")

            # Fetch article content once and reuse it
            article_html = fetch_page(full_url)
            content, pub_date = get_article_content(article_html)

            if content:
                description = content[:500] + "..." if len(content) > 500 else content
            else:
                description = "No description available"

            blog_post = {
                "title": title,
                "link": full_url,
                "description": description,
                "date": pub_date or stable_fallback_date(full_url),  # Fallback to stable date if none found
            }

            # There are a handful (~7) old blog posts where parsing the date doesn't work very well.
            # In order to avoid sending hourly emails for this, we're just skipping them altogether.
            # We can spend more time on this if/when it ever becomes an issue.
            if pub_date:
                blog_posts.append(blog_post)
            else:
                logger.warning(f"Skipping post '{title}' - no date found")

        logger.info(f"Successfully parsed {len(blog_posts)} blog posts")
        return blog_posts

    except Exception as e:
        logger.error(f"Error parsing HTML content: {e!s}")
        raise


def generate_rss_feed(blog_posts):
    """Generate RSS feed from blog posts."""
    try:
        fg = FeedGenerator()
        fg.title("Paul Graham Essays")
        fg.description("Essays by Paul Graham")
        fg.language("en")

        # Set feed metadata
        fg.author({"name": "Paul Graham"})
        fg.subtitle("Paul Graham's Essays and Writings")
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
        blog_posts = parse_essays_page(html_content)

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
