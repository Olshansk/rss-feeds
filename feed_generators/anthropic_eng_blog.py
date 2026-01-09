import requests
from bs4 import BeautifulSoup
from datetime import datetime
import pytz
from feedgen.feed import FeedGenerator
import logging
from pathlib import Path

from utils import sort_posts_for_feed

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


def fetch_engineering_content(url="https://www.anthropic.com/engineering"):
    """Fetch engineering page content from Anthropic's website."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        logger.error(f"Error fetching engineering content: {str(e)}")
        raise


def validate_article(article):
    """Validate article has required fields."""
    if not article.get("title") or len(article["title"]) < 5:
        return False
    if not article.get("link") or not article["link"].startswith("http"):
        return False
    if not article.get("date"):
        return False
    return True


def parse_engineering_html(html_content):
    """Parse the engineering HTML content and extract article information from embedded JSON."""
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        articles = []

        # Find the Next.js script tag containing article data
        script_tag = None
        for script in soup.find_all("script"):
            if script.string and "publishedOn" in script.string and "engineeringArticle" in script.string:
                script_tag = script
                break

        if not script_tag:
            logger.error("Could not find Next.js data script containing article information")
            return []

        script_content = script_tag.string

        # Extract article data from the escaped JSON in the Next.js script
        # Pattern matches: publishedOn, slug, title, and summary fields
        import re

        pattern = r'\\"publishedOn\\":\\"([^"]+?)\\",\\"slug\\":\{[^}]*?\\"current\\":\\"([^"]+?)\\"'
        matches = re.findall(pattern, script_content)

        logger.info(f"Found {len(matches)} articles from JSON data")

        for published_date, slug in matches:
            try:
                # Construct the full URL from the slug
                link = f"https://www.anthropic.com/engineering/{slug}"

                # Find the article object containing this slug to get title and summary
                # Search for the section containing this slug
                slug_pos = script_content.find(f'\\"current\\":\\"{slug}\\"')
                if slug_pos == -1:
                    continue

                # Search forward from slug position to find the title and summary
                # The structure is: ...publishedOn, slug, ...other fields..., summary, title}
                search_section = script_content[slug_pos:slug_pos + 2000]

                # Extract title and summary (they appear AFTER the slug in the data)
                # Use negative lookbehind to handle escaped quotes correctly
                title_match = re.search(r'\\"title\\":\\"(.*?)(?<!\\)\\"', search_section)
                title = title_match.group(1) if title_match else slug.replace("-", " ").title()
                # Unescape the title using re.sub to handle all escaped characters
                title = re.sub(r'\\(.)', r'\1', title) if title else title

                # Extract summary/description
                summary_match = re.search(r'\\"summary\\":\\"(.*?)(?<!\\)\\"', search_section)
                description = summary_match.group(1) if summary_match else title
                # Unescape the description
                description = re.sub(r'\\(.)', r'\1', description) if description else description

                # Parse the date
                date = datetime.strptime(published_date, "%Y-%m-%d")
                date = date.replace(hour=0, minute=0, second=0, tzinfo=pytz.UTC)

                article = {
                    "title": title,
                    "link": link,
                    "description": description if description else title,
                    "date": date,
                    "category": "Engineering",
                }

                if validate_article(article):
                    articles.append(article)
                    logger.info(f"Found article: {title} ({published_date})")

            except Exception as e:
                logger.warning(f"Error parsing article {slug}: {str(e)}")
                continue

        logger.info(f"Successfully parsed {len(articles)} articles from JSON data")
        return articles

    except Exception as e:
        logger.error(f"Error parsing HTML content: {str(e)}")
        raise


def generate_rss_feed(articles, feed_name="anthropic_engineering"):
    """Generate RSS feed from engineering articles."""
    try:
        fg = FeedGenerator()
        fg.title("Anthropic Engineering Blog")
        fg.description("Latest engineering articles and insights from Anthropic's engineering team")
        fg.link(href="https://www.anthropic.com/engineering")
        fg.language("en")

        # Set feed metadata
        fg.author({"name": "Anthropic Engineering Team"})
        fg.logo("https://www.anthropic.com/images/icons/apple-touch-icon.png")
        fg.subtitle("Inside the team building reliable AI systems")
        fg.link(href="https://www.anthropic.com/engineering", rel="alternate")
        fg.link(href=f"https://anthropic.com/engineering/feed_{feed_name}.xml", rel="self")

        # Sort articles for correct feed order (newest first in output)
        articles_sorted = sort_posts_for_feed(articles, date_field="date")

        # Add entries
        for article in articles_sorted:
            fe = fg.add_entry()
            fe.title(article["title"])
            fe.description(article["description"])
            fe.link(href=article["link"])
            fe.published(article["date"])
            fe.category(term=article["category"])
            fe.id(article["link"])

        logger.info("Successfully generated RSS feed")
        return fg

    except Exception as e:
        logger.error(f"Error generating RSS feed: {str(e)}")
        raise


def save_rss_feed(feed_generator, feed_name="anthropic_engineering"):
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


def main(feed_name="anthropic_engineering"):
    """Main function to generate RSS feed from Anthropic's engineering page."""
    try:
        # Fetch engineering content
        html_content = fetch_engineering_content()

        # Parse articles from HTML
        articles = parse_engineering_html(html_content)

        if not articles:
            logger.warning("No articles found on the engineering page")
            return False

        # Generate RSS feed
        feed = generate_rss_feed(articles, feed_name)

        # Save feed to file
        output_file = save_rss_feed(feed, feed_name)

        logger.info(f"Successfully generated RSS feed with {len(articles)} articles")
        return True

    except Exception as e:
        logger.error(f"Failed to generate RSS feed: {str(e)}")
        return False


if __name__ == "__main__":
    main()
