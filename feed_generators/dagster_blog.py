import logging
from datetime import datetime
from pathlib import Path

import pytz
import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def get_project_root():
    """Get the project root directory."""
    # Since this script is in feed_generators/dagster_blog.py,
    # we need to go up one level to reach the project root
    return Path(__file__).parent.parent


def ensure_feeds_directory():
    """Ensure the feeds directory exists."""
    feeds_dir = get_project_root() / "feeds"
    feeds_dir.mkdir(exist_ok=True)
    return feeds_dir


def fetch_blog_content(url):
    """Fetch blog content from the given URL."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        logger.error(f"Error fetching blog content: {str(e)}")
        raise


def parse_blog_html(html_content):
    """Parse the blog HTML content and extract post information."""
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        blog_posts = []

        # First, parse the featured blog post (if present)
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

                # Convert relative URLs to absolute URLs
                if link.startswith("/"):
                    link = f"https://dagster.io{link}"

                if link:
                    blog_posts.append(
                        {
                            "title": title,
                            "date": date_obj,
                            "description": description,
                            "link": link,
                        }
                    )

        # Find all regular blog post cards
        posts = soup.select("div.blog_card")

        for post in posts:
            # Extract title
            title_elem = post.select_one("h3.blog_card_title")
            if not title_elem:
                continue
            title = title_elem.text.strip()

            # Extract date
            date_elem = post.select_one("p.text-color-neutral-500.text-size-small")
            if not date_elem:
                continue
            date_str = date_elem.text.strip()
            # Parse date format: "December 22, 2025"
            date_obj = datetime.strptime(date_str, "%B %d, %Y")

            # Extract description
            description_elem = post.select_one('p[fs-cmsfilter-field="description"]')
            description = description_elem.text.strip() if description_elem else ""

            # Extract link - find the clickable_link within the card
            link_elem = post.select_one("a.clickable_link")
            if not link_elem or not link_elem.get("href"):
                continue
            link = link_elem["href"]

            # Convert relative URLs to absolute URLs
            if link.startswith("/"):
                link = f"https://dagster.io{link}"

            blog_posts.append(
                {
                    "title": title,
                    "date": date_obj,
                    "description": description,
                    "link": link,
                }
            )

        logger.info(f"Successfully parsed {len(blog_posts)} blog posts")
        return blog_posts

    except Exception as e:
        logger.error(f"Error parsing HTML content: {str(e)}")
        raise


def generate_rss_feed(blog_posts, feed_name="dagster"):
    """Generate RSS feed from blog posts."""
    try:
        fg = FeedGenerator()
        fg.title("Dagster Blog")
        fg.description(
            "Read the latest from the Dagster team: insights, tutorials, and updates on data engineering, orchestration, and building better pipelines."
        )
        fg.link(href="https://dagster.io/blog")
        fg.language("en")

        # Set feed metadata
        fg.author({"name": "Dagster"})
        fg.subtitle("Latest updates from Dagster")
        fg.link(href="https://dagster.io/blog", rel="alternate")
        fg.link(href=f"https://dagster.io/blog/feed_{feed_name}.xml", rel="self")

        # Add entries
        for post in blog_posts:
            fe = fg.add_entry()
            fe.title(post["title"])
            fe.description(post["description"])
            fe.link(href=post["link"])
            fe.published(post["date"].replace(tzinfo=pytz.UTC))
            fe.id(post["link"])

        logger.info("Successfully generated RSS feed")
        return fg

    except Exception as e:
        logger.error(f"Error generating RSS feed: {str(e)}")
        raise


def save_rss_feed(feed_generator, feed_name="dagster"):
    """Save the RSS feed to a file in the feeds directory."""
    try:
        # Ensure feeds directory exists and get its path
        feeds_dir = ensure_feeds_directory()

        # Create the output file path
        output_filename = feeds_dir / f"feed_{feed_name}.xml"

        # Save the feed
        feed_generator.rss_file(str(output_filename), pretty=True)
        logger.info(f"Successfully saved RSS feed to {output_filename}")
        return output_filename

    except Exception as e:
        logger.error(f"Error saving RSS feed: {str(e)}")
        raise


def main(blog_url="https://dagster.io/blog", feed_name="dagster"):
    """Main function to generate RSS feed from blog URL."""
    try:
        # Fetch blog content
        html_content = fetch_blog_content(blog_url)

        # Parse blog posts from HTML
        blog_posts = parse_blog_html(html_content)

        # Generate RSS feed
        feed = generate_rss_feed(blog_posts, feed_name)

        # Save feed to file
        output_file = save_rss_feed(feed, feed_name)

        return True

    except Exception as e:
        logger.error(f"Failed to generate RSS feed: {str(e)}")
        return False


if __name__ == "__main__":
    main()
