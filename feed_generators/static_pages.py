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
