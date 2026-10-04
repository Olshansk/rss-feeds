"""Bounded HTTP fetching for static pages and native feeds."""

import requests

DEFAULT_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36"
DEFAULT_HEADERS = {"User-Agent": DEFAULT_USER_AGENT}


def fetch_page(url: str, timeout: int = 30, headers: dict | None = None) -> str:
    """Fetch a page and return its HTML content.

    Args:
        url: URL to fetch
        timeout: Request timeout in seconds
        headers: Optional headers dict. Falls back to DEFAULT_HEADERS.

    Returns:
        Response text (HTML)
    """
    if headers is None:
        headers = DEFAULT_HEADERS
    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()
    return response.text


def fetch_paginated(url, parse, next_url, max_pages=100):
    """Fetch a bounded sequence of static listings, deduplicating overlapping cards.

    How:
    1. Fetch each unvisited URL and require a nonempty parser result.
    2. Merge cards by URL and follow the source-specific next-page link.
    3. Stop at the page limit or the end of the listing; reject pagination loops.
    """
    seen, posts = set(), {}
    for _ in range(max_pages):
        if not url:
            break
        if url in seen:
            raise ValueError(f"Pagination loop at {url}")
        seen.add(url)
        html = fetch_page(url)
        current = parse(html)
        if not current:
            raise ValueError(f"No live posts extracted from {url}")
        posts.update({post["link"]: post for post in current})
        url = next_url(html, url)
    return list(posts.values())
