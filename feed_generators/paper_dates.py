"""Publication-date enrichment for research listings with year-only metadata."""

import re
from datetime import UTC, datetime
from xml.etree import ElementTree as ET

import requests

from dates import parse_date
from static_pages import DEFAULT_HEADERS

ARXIV = re.compile(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})")


def enrich_paper_dates(posts):
    """Use original arXiv publication dates and label year-only dates explicitly.

    How:
    1. Collect arXiv IDs whose exact dates were not supplied by the listing.
    2. Fetch their publication metadata in one bounded API request.
    3. Require dates for those papers; represent other year-only records at January 1.
    """
    ids = {match.group(1) for post in posts if not post.get("date") and (match := ARXIV.search(post["link"]))}
    dates = {}
    if ids:
        response = requests.get(
            "https://export.arxiv.org/api/query",
            params={"id_list": ",".join(sorted(ids)), "max_results": len(ids)},
            headers=DEFAULT_HEADERS,
            timeout=60,
        )
        response.raise_for_status()
        ns = {"a": "http://www.w3.org/2005/Atom"}
        for item in ET.fromstring(response.content).findall("a:entry", ns):
            match = ARXIV.search(item.findtext("a:id", default="", namespaces=ns))
            if match:
                dates[match.group(1)] = parse_date(item.findtext("a:published", namespaces=ns))
        if ids - dates.keys():
            raise ValueError(f"arXiv omitted dates for {sorted(ids - dates.keys())}")
    enriched = []
    for post in posts:
        post = post.copy()
        if not post.get("date"):
            match = ARXIV.search(post["link"])
            if match:
                post["date"] = dates[match.group(1)]
            else:
                year = int(post["year"])
                post["date"] = datetime(year, 1, 1, tzinfo=UTC)
                post["description"] += (
                    f" (Source provides publication year {year} only; January 1 represents that year.)"
                )
        enriched.append(post)
    return enriched
