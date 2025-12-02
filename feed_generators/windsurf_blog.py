import requests
from datetime import datetime
import pytz
from feedgen.feed import FeedGenerator
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def get_project_root():
    """Get the project root directory."""
    return Path(__file__).parent.parent


def ensure_feeds_directory():
    """Ensure the feeds directory exists."""
    feeds_dir = get_project_root() / "feeds"
    feeds_dir.mkdir(exist_ok=True)
    return feeds_dir


def fetch_blog_posts():
    """Fetch blog posts from Windsurf's API."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
            "Accept": "*/*",
        }
        url = "https://windsurf.com/api/blog"
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"Error fetching blog posts: {str(e)}")
        raise


def parse_blog_posts(api_response):
    """Parse blog posts from API response."""
    try:
        posts = api_response.get("posts", [])
        blog_posts = []

        for post in posts:
            # Skip drafts
            if post.get("draft", False):
                continue

            title = post.get("title", "")
            if not title:
                continue

            # Parse date
            date_str = post.get("date", "")
            if date_str:
                try:
                    date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                except ValueError:
                    date = datetime.now(pytz.UTC)
            else:
                date = datetime.now(pytz.UTC)

            # Build link from slug
            slug = post.get("slug", "")
            link = f"https://windsurf.com/blog/{slug}" if slug else "https://windsurf.com/blog"

            # Get summary/description
            description = post.get("summary", title)

            # Get tags for categories
            tags = post.get("tags", [])

            blog_posts.append({
                "title": title,
                "link": link,
                "description": description,
                "date": date,
                "tags": tags,
            })

        logger.info(f"Successfully parsed {len(blog_posts)} blog posts")
        return blog_posts

    except Exception as e:
        logger.error(f"Error parsing blog posts: {str(e)}")
        raise


def generate_rss_feed(blog_posts, feed_name="windsurf_blog"):
    """Generate RSS feed from blog posts."""
    try:
        fg = FeedGenerator()
        fg.title("Windsurf Blog")
        fg.description("Latest updates and announcements from Windsurf")
        fg.link(href="https://windsurf.com/blog")
        fg.language("en")

        fg.author({"name": "Windsurf"})
        fg.subtitle("Read about the latest announcements from Windsurf")
        fg.link(href="https://windsurf.com/blog", rel="alternate")
        fg.link(href=f"https://windsurf.com/blog/feed_{feed_name}.xml", rel="self")

        # Sort by date (newest first)
        blog_posts_sorted = sorted(blog_posts, key=lambda x: x["date"], reverse=True)

        for post in blog_posts_sorted:
            fe = fg.add_entry()
            fe.title(post["title"])
            fe.description(post["description"])
            fe.link(href=post["link"])
            fe.published(post["date"])
            fe.id(post["link"])

            # Add tags as categories
            for tag in post.get("tags", []):
                fe.category(term=tag)

        logger.info("Successfully generated RSS feed")
        return fg

    except Exception as e:
        logger.error(f"Error generating RSS feed: {str(e)}")
        raise


def save_rss_feed(feed_generator, feed_name="windsurf_blog"):
    """Save the RSS feed to a file in the feeds directory."""
    try:
        feeds_dir = ensure_feeds_directory()
        output_filename = feeds_dir / f"feed_{feed_name}.xml"
        feed_generator.rss_file(str(output_filename), pretty=True)
        logger.info(f"Successfully saved RSS feed to {output_filename}")
        return output_filename
    except Exception as e:
        logger.error(f"Error saving RSS feed: {str(e)}")
        raise


def main(feed_name="windsurf_blog"):
    """Main function to generate RSS feed from Windsurf blog."""
    try:
        api_response = fetch_blog_posts()
        blog_posts = parse_blog_posts(api_response)

        if not blog_posts:
            logger.warning("No blog posts found!")
            return False

        feed = generate_rss_feed(blog_posts, feed_name)
        output_file = save_rss_feed(feed, feed_name)

        logger.info(f"Successfully generated RSS feed with {len(blog_posts)} posts")
        return True

    except Exception as e:
        logger.error(f"Failed to generate RSS feed: {str(e)}")
        return False


if __name__ == "__main__":
    main()
