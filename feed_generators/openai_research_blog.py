import requests
from bs4 import BeautifulSoup
from datetime import datetime
import pytz
from feedgen.feed import FeedGenerator
import logging
from pathlib import Path
import re

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


def fetch_blog_content(url):
    """Fetch blog content from the given URL."""
    try:
        # Create a session object to maintain cookies
        session = requests.Session()

        # More complete browser headers
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            # Don't accept compressed content for now
            "Accept-Encoding": "identity",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
        }

        # Add headers to session
        session.headers.update(headers)

        # Make the request without accepting compression
        response = session.get(url, timeout=10)
        response.raise_for_status()

        # Print response headers for debugging
        print("=== Response Headers ===")
        print(dict(response.headers))
        print("\n")

        # Print the first 1000 chars of response text
        print("=== Response Text Preview ===")
        print(response.text[:1000])
        print("\n")

        return response.text
    except requests.RequestException as e:
        logger.error(f"Error fetching blog content: {str(e)}")
        raise


def parse_date(date_str):
    """Parse date string to datetime object."""
    try:
        # Convert date format like "Dec 9, 2024" to datetime
        return datetime.strptime(date_str.strip(), "%b %d, %Y").replace(tzinfo=pytz.UTC)
    except ValueError as e:
        logger.error(f"Error parsing date '{date_str}': {str(e)}")
        return None


def parse_blog_html(html_content):
    """Parse the blog HTML content and extract post information."""
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        blog_posts = []

        # Debug: Print the first 1000 characters of raw HTML
        print("=== Raw HTML Preview ===")
        print(html_content[:1000])
        print("\n---\n")

        # Debug: Print all grid divs
        print("=== All Grid Divs ===")
        grid_divs = soup.find_all("div", class_="grid")
        for div in grid_divs:
            print("Found grid div:")
            print(div.prettify())
            print("\n---\n")

        # Debug: Print all col-span-1 divs
        print("=== All Col-Span-1 Divs ===")
        col_divs = soup.find_all("div", class_="col-span-1")
        for div in col_divs:
            print("Found col-span div:")
            print(div.prettify())
            print("\n---\n")

        # Debug: Print all index links
        print("=== All Index Links ===")
        links = soup.find_all("a", href=lambda x: x and x.startswith("/index/"))
        for link in links:
            print("Found link:")
            print(link.prettify())
            print("\n---\n")

        # Now try to parse any links we found
        for link in links:
            try:
                # Extract title
                title_elem = link.select_one("div.line-clamp-4")
                title = title_elem.get_text(strip=True) if title_elem else None

                # Extract date
                date_elem = link.select_one("span.text-small")
                date_str = date_elem.get_text(strip=True) if date_elem else None
                pub_date = parse_date(date_str) if date_str else None

                # Build link
                article_link = f"https://openai.com{link['href']}"

                if title and pub_date:
                    blog_posts.append(
                        {"title": title, "date": pub_date, "description": "OpenAI Research", "link": article_link}
                    )
            except Exception as e:
                logger.warning(f"Error parsing article: {str(e)}")
                continue

        logger.info(f"Successfully parsed {len(blog_posts)} blog posts")
        return blog_posts

    except Exception as e:
        logger.error(f"Error parsing HTML content: {str(e)}")
        raise

        for article in article_links:
            try:
                # Extract title from the line-clamp div
                title_elem = article.select_one("div.line-clamp-4")
                title = title_elem.get_text(strip=True) if title_elem else None

                # Extract date from the span with text-small class
                date_elem = article.select_one("span[class*='text-small']")
                date_str = date_elem.get_text(strip=True) if date_elem else None
                pub_date = parse_date(date_str) if date_str else None

                # For description, use the category if available, otherwise use a default
                description = "OpenAI Research"

                # Extract link
                link = f"https://openai.com{article['href']}"

                if title and pub_date:
                    blog_posts.append({"title": title, "date": pub_date, "description": description, "link": link})
            except Exception as e:
                logger.warning(f"Error parsing article: {str(e)}")
                continue

        logger.info(f"Successfully parsed {len(blog_posts)} blog posts")
        return blog_posts

    except Exception as e:
        logger.error(f"Error parsing HTML content: {str(e)}")
        raise


def generate_rss_feed(blog_posts, feed_name="openai_research"):
    """Generate RSS feed from blog posts."""
    try:
        fg = FeedGenerator()
        fg.title("OpenAI Research Blog")
        fg.description("Latest research updates from OpenAI")
        fg.link(href="https://openai.com/research")
        fg.language("en")

        # Set feed metadata
        fg.author({"name": "OpenAI"})
        fg.logo("https://openai.com/favicon.ico")
        fg.subtitle("Research publications and updates from OpenAI")
        fg.link(href="https://openai.com/news/research", rel="alternate")
        fg.link(href=f"https://openai.com/feed_{feed_name}.xml", rel="self")

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


def save_rss_feed(feed_generator, feed_name="openai_research"):
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


def main(blog_url="https://openai.com/news/research", feed_name="openai_research"):
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
