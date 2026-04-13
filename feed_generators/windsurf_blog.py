from datetime import datetime

import pytz
import requests
from feedgen.feed import FeedGenerator

from utils import save_rss_feed, setup_feed_links, setup_logging, sort_posts_for_feed

logger = setup_logging()

FEED_NAME = "windsurf_blog"  # keep _blog suffix for backwards compatibility (feed URL)
BLOG_URL = "https://windsurf.com/blog"


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
        logger.error(f"Error fetching blog posts: {e!s}")
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

            blog_posts.append(
                {
                    "title": title,
                    "link": link,
                    "description": description,
                    "date": date,
                    "tags": tags,
                }
            )

        logger.info(f"Successfully parsed {len(blog_posts)} blog posts")
        return blog_posts

    except Exception as e:
        logger.error(f"Error parsing blog posts: {e!s}")
        raise


def generate_rss_feed(blog_posts, feed_name=FEED_NAME):
    """Generate RSS feed from blog posts."""
    try:
        fg = FeedGenerator()
        fg.title("Windsurf Blog")
        fg.description("Latest updates and announcements from Windsurf")
        setup_feed_links(fg, BLOG_URL, feed_name)
        fg.language("en")

        fg.author({"name": "Windsurf"})
        fg.subtitle("Read about the latest announcements from Windsurf")

        # Sort for correct feed order (newest first in output)
        blog_posts_sorted = sort_posts_for_feed(blog_posts, date_field="date")

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
        logger.error(f"Error generating RSS feed: {e!s}")
        raise


def main(feed_name=FEED_NAME):
    """Main function to generate RSS feed from Windsurf blog."""
    try:
        api_response = fetch_blog_posts()
        blog_posts = parse_blog_posts(api_response)

        if not blog_posts:
            logger.warning("No blog posts found!")
            return False

        feed = generate_rss_feed(blog_posts, feed_name)
        save_rss_feed(feed, feed_name)

        logger.info(f"Successfully generated RSS feed with {len(blog_posts)} posts")
        return True

    except Exception as e:
        logger.error(f"Failed to generate RSS feed: {e!s}")
        return False


if __name__ == "__main__":
    main()
