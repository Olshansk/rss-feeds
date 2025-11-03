#!/usr/bin/env python3
"""
RSS Feed Generator for Surge AI Blog
Scrapes https://www.surgehq.ai/blog and generates an RSS feed
"""

import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
from datetime import datetime
from dateutil import parser
import pytz

def generate_blogsurgeai_feed():
    """Generate RSS feed for Surge AI blog"""

    # Initialize feed generator
    fg = FeedGenerator()
    fg.id('https://www.surgehq.ai/blog')
    fg.title('Surge AI Blog')
    fg.author({'name': 'Surge AI', 'email': 'team@surgehq.ai'})
    fg.link(href='https://www.surgehq.ai/blog', rel='alternate')
    fg.link(href='https://raw.githubusercontent.com/olshansky/rss-feeds/main/feeds/feed_blogsurgeai.xml', rel='self')
    fg.language('en')
    fg.description('New methods, current trends & software infrastructure for NLP. Articles written by our senior engineering leads from Google, Facebook, Twitter, Harvard, MIT, and Y Combinator')

    # Fetch the blog page
    url = 'https://www.surgehq.ai/blog'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
    except Exception as e:
        print(f"Error fetching blog page: {e}")
        return

    # Parse HTML
    soup = BeautifulSoup(response.content, 'html.parser')

    # Find all blog post items
    blog_items = soup.find_all('div', class_='blog-hero-cms-item')

    print(f"Found {len(blog_items)} blog posts")

    # Process each blog post
    for item in blog_items:
        try:
            # Find the title
            title_element = item.find('div', class_='blog-hero-cms-item-title')
            if not title_element:
                continue

            title = title_element.get_text(strip=True)

            # Find the link
            link_element = item.find('a', class_='blog-hero-cms-item-link')
            if not link_element:
                continue

            link = link_element.get('href')
            if not link.startswith('http'):
                link = 'https://www.surgehq.ai' + link

            # Find the description
            desc_element = item.find('div', class_='blog-hero-cms-item-desc')
            description = desc_element.get_text(strip=True) if desc_element else title

            # Find the date
            date_element = item.find('div', class_='blog-hero-cms-item-date')
            pub_date = datetime.now(pytz.UTC)  # Default fallback

            if date_element:
                # Find the visible date element (the one without w-condition-invisible)
                date_texts = date_element.find_all('div', class_='txt fs-12 inline')
                for date_text in date_texts:
                    if 'w-condition-invisible' not in date_text.get('class', []):
                        date_str = date_text.get_text(strip=True)
                        try:
                            # Parse the date string (e.g., "October 10, 2025")
                            pub_date = parser.parse(date_str)
                            # Make timezone-aware
                            if pub_date.tzinfo is None:
                                pub_date = pytz.UTC.localize(pub_date)
                            break
                        except Exception as e:
                            print(f"Could not parse date '{date_str}': {e}")

            # Create feed entry
            fe = fg.add_entry()
            fe.id(link)
            fe.title(title)
            fe.link(href=link)
            fe.published(pub_date)

            # Set description
            fe.description(description)

            print(f"Added: {title}")

        except Exception as e:
            print(f"Error processing blog item: {e}")
            continue

    # Generate RSS feed
    output_path = 'feeds/feed_blogsurgeai.xml'
    fg.rss_file(output_path, pretty=True)
    print(f"\nRSS feed generated successfully: {output_path}")

if __name__ == '__main__':
    generate_blogsurgeai_feed()
