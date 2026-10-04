"""Semantic article-card parsing shared across static and rendered listings."""

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from dates import parse_date

DATE_TEXT = re.compile(r"\b[A-Za-z]{3,9}\.? \d{1,2},? \d{4}\b")


def parse_dated_cards(html, selector, base_url, *, parent=False, title_selector="h1, h2, h3, h4"):
    """Extract unique titled links with dates from cards or their parent containers.

    How:
    1. Select article anchors or containers and locate their semantic headings.
    2. Read ISO time attributes or a complete visible publication date.
    3. Resolve links, retain summaries, and deduplicate featured cards.
    """
    posts = {}
    for element in BeautifulSoup(html, "html.parser").select(selector):
        card = element.parent if parent else element
        anchor = element if element.has_attr("href") else element.select_one("a[href]")
        heading = card.select_one(title_selector)
        if heading is None or anchor is None:
            continue
        time = card.select_one("time[datetime]")
        match = DATE_TEXT.search(card.get_text(" ", strip=True))
        date_text = time["datetime"] if time else match.group() if match else ""
        date = parse_date(date_text)
        link = urljoin(base_url, anchor["href"])
        title = heading.get_text(" ", strip=True)
        summary = card.find("p")
        posts[link] = {
            "title": title,
            "link": link,
            "date": date,
            "description": summary.get_text(" ", strip=True) if summary else title,
        }
    return list(posts.values())
