"""Fetch public JSON listings that expose numbered pages and a total count."""

import json
from urllib.parse import urlencode

from static_pages import fetch_page


def fetch_numbered_items(url, *, params=None, full=False, max_pages=100, require_complete=True):
    """Read a fresh first page or a complete listing, rejecting incomplete pagination.

    How:
    1. Fetch numbered JSON pages with the shared bounded HTTP client.
    2. Validate the items and total count, requiring new item identities on every page.
    3. Stop after the first page or advertised total; only explicit bounded-window callers may truncate.
    """
    items = {}
    for page in range(1, max_pages + 1):
        payload = json.loads(fetch_page(f"{url}?{urlencode({**(params or {}), 'page': page})}"))
        batch, total = payload.get("items"), payload.get("total")
        if not isinstance(batch, list) or not isinstance(total, int) or total < 1:
            raise ValueError("Invalid or empty JSON listing")
        previous_count = len(items)
        for item in batch:
            if not isinstance(item, dict) or not item.get("_id"):
                raise ValueError("JSON listing item lacks an identity")
            items[item["_id"]] = item
        if len(items) == previous_count:
            raise ValueError(f"JSON pagination stopped making progress on page {page}")
        if not full or len(items) >= total:
            return list(items.values())
    if require_complete:
        raise ValueError(f"JSON pagination exceeded {max_pages} pages")
    return list(items.values())
