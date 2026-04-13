from datetime import datetime

import pytz
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator

from utils import fetch_page, save_rss_feed, setup_feed_links, setup_logging, sort_posts_for_feed, stable_fallback_date

logger = setup_logging()

FEED_NAME = "anthropic_red"
BLOG_URL = "https://red.anthropic.com/"


def fetch_red_content(url=BLOG_URL):
    """Fetch content from Anthropic's red team blog."""
    try:
        return fetch_page(url)
    except Exception as e:
        logger.error(f"Error fetching red team blog content: {e!s}")
        raise


def parse_date(date_text):
    """Parse date text from article pages (e.g., 'November 12, 2025', 'September 29, 2025')."""
    date_formats = [
        "%B %d, %Y",  # November 12, 2025
        "%b %d, %Y",  # Nov 12, 2025
        "%B %Y",  # November 2025 (fallback)
        "%b %Y",  # Nov 2025 (fallback)
    ]

    for date_format in date_formats:
        try:
            date = datetime.strptime(date_text, date_format)
            return date.replace(tzinfo=pytz.UTC)
        except ValueError:
            continue

    logger.warning(f"Could not parse date: {date_text}")
    return None


def fetch_article_date(article_url):
    """Fetch the publication date from an individual article page."""
    try:
        html = fetch_page(article_url)

        soup = BeautifulSoup(html, "html.parser")

        # Look for date in d-article section
        article_section = soup.select_one("d-article")
        if article_section:
            # The date is typically in the first <p> tag
            first_p = article_section.select_one("p")
            if first_p:
                date_text = first_p.text.strip()
                date = parse_date(date_text)
                if date:
                    logger.debug(f"Found date '{date_text}' for {article_url}")
                    return date

        logger.warning(f"Could not find date in article: {article_url}")
        return None

    except Exception as e:
        logger.warning(f"Error fetching article date from {article_url}: {e!s}")
        return None


def parse_red_html(html_content):
    """Parse the red team blog HTML content and extract article information."""
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        articles = []
        seen_links = set()

        # Find all article links across the entire page (TOC + body sections)
        all_notes = soup.select("a.note")
        logger.info(f"Found {len(all_notes)} potential article links")

        # Build a map of date dividers for context
        date_sections = {}
        for date_div in soup.select("div.date"):
            date_text = date_div.text.strip()
            parsed = parse_date(date_text)
            if parsed:
                date_sections[date_text] = parsed

        for article_link in all_notes:
            # Extract article information
            href = article_link.get("href", "")
            if not href:
                continue

            # Build full URL
            if href.startswith("http"):
                link = href
            elif href.startswith("/"):
                link = f"https://red.anthropic.com{href}"
            else:
                link = f"https://red.anthropic.com/{href}"

            # Skip duplicates
            if link in seen_links:
                continue
            seen_links.add(link)

            # Extract title
            title_elem = article_link.select_one("h3")
            if not title_elem:
                logger.warning(f"Could not extract title for link: {link}")
                continue
            title = title_elem.text.strip()

            # Extract description
            description_elem = article_link.select_one("div.description")
            description = description_elem.text.strip() if description_elem else title

            # Fetch actual publication date from the article page
            article_date = fetch_article_date(link)

            # Fallback to stable date if fetching fails
            if not article_date:
                article_date = stable_fallback_date(link)
                logger.warning(f"Using fallback date for article: {title}")

            # Create article object
            article = {
                "title": title,
                "link": link,
                "date": article_date,
                "description": description,
            }

            articles.append(article)
            logger.debug(f"Found article: {title} (date: {article_date})")

        logger.info(f"Successfully parsed {len(articles)} articles")
        return articles

    except Exception as e:
        logger.error(f"Error parsing HTML content: {e!s}")
        raise


def generate_rss_feed(articles, feed_name=FEED_NAME):
    """Generate RSS feed from red team blog articles."""
    try:
        fg = FeedGenerator()
        fg.title("Anthropic Frontier Red Team Blog")
        fg.description(
            "Research from Anthropic's Frontier Red Team on what frontier AI models mean for national security"
        )
        setup_feed_links(fg, BLOG_URL, feed_name)
        fg.language("en")

        # Set feed metadata
        fg.author({"name": "Anthropic Frontier Red Team"})
        fg.logo("https://www.anthropic.com/images/icons/apple-touch-icon.png")
        fg.subtitle(
            "Evidence-based analysis about AI's implications for cybersecurity, biosecurity, and autonomous systems"
        )

        # Sort articles for correct feed order (newest first in output)
        sorted_articles = sort_posts_for_feed(articles, date_field="date")

        # Add entries
        for article in sorted_articles:
            fe = fg.add_entry()
            fe.title(article["title"])
            fe.description(article["description"])
            fe.link(href=article["link"])
            fe.published(article["date"])
            fe.id(article["link"])

        logger.info("Successfully generated RSS feed")
        return fg

    except Exception as e:
        logger.error(f"Error generating RSS feed: {e!s}")
        raise


def main(feed_name=FEED_NAME):
    """Main function to generate RSS feed from Anthropic's red team blog."""
    try:
        # Fetch blog content
        html_content = fetch_red_content()

        # Parse articles from HTML
        articles = parse_red_html(html_content)

        if not articles:
            logger.warning("No articles found")
            return False

        # Generate RSS feed
        feed = generate_rss_feed(articles, feed_name)

        # Save feed to file
        save_rss_feed(feed, feed_name)

        logger.info(f"Successfully generated RSS feed with {len(articles)} articles")
        return True

    except Exception as e:
        logger.error(f"Failed to generate RSS feed: {e!s}")
        return False


if __name__ == "__main__":
    main()
