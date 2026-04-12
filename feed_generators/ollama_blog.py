from datetime import datetime

import pytz
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator

from utils import (
    fetch_page,
    save_rss_feed,
    setup_feed_links,
    setup_logging,
)

logger = setup_logging()

FEED_NAME = "ollama"
BLOG_URL = "https://ollama.com/blog"


def fetch_blog_content(url=BLOG_URL):
    """Fetch blog content from the given URL."""
    try:
        return fetch_page(url)
    except Exception as e:
        logger.error(f"Error fetching blog content: {str(e)}")
        raise


def parse_blog_html(html_content):
    """Parse the blog HTML content and extract post information."""
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        blog_posts = []

        # Find all blog post sections
        posts = soup.select('section a[href^="/blog/"]')

        for post in posts:
            # Extract title
            title = post.select_one("h2").text.strip()

            # Extract date
            date_str = post.select_one("h3").text.strip()
            date_obj = datetime.strptime(date_str, "%B %d, %Y")

            # Extract description
            description = post.select_one("p").text.strip()

            # Extract link
            link = f"https://ollama.com{post['href']}"

            blog_posts.append({"title": title, "date": date_obj, "description": description, "link": link})

        logger.info(f"Successfully parsed {len(blog_posts)} blog posts")
        return blog_posts

    except Exception as e:
        logger.error(f"Error parsing HTML content: {str(e)}")
        raise


def generate_rss_feed(blog_posts, feed_name=FEED_NAME):
    """Generate RSS feed from blog posts."""
    try:
        fg = FeedGenerator()
        fg.title("Ollama Blog")
        fg.description("Get up and running with large language models.")
        setup_feed_links(fg, BLOG_URL, feed_name)
        fg.language("en")

        # Set feed metadata
        fg.author({"name": "Ollama"})
        fg.logo("https://ollama.com/public/icon-64x64.png")
        fg.subtitle("Latest updates from Ollama")

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


def main(blog_url=BLOG_URL, feed_name=FEED_NAME):
    """Main function to generate RSS feed from blog URL."""
    try:
        # Fetch blog content
        html_content = fetch_blog_content(blog_url)

        # Parse blog posts from HTML
        blog_posts = parse_blog_html(html_content)

        # Generate RSS feed
        feed = generate_rss_feed(blog_posts, feed_name)

        # Save feed to file
        save_rss_feed(feed, feed_name)

        return True

    except Exception as e:
        logger.error(f"Failed to generate RSS feed: {str(e)}")
        return False


if __name__ == "__main__":
    main()
