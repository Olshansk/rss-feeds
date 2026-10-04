"""Shared Mintlify changelog parsing with stable pre-migration identities."""

import logging
import re

from bs4 import BeautifulSoup

from dates import parse_date

logger = logging.getLogger(__name__)


def parse_changelog(html_content, blog_url, title_prefix, legacy_url):
    """Parse the changelog HTML content and extract version entries."""
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        changelog_entries = []

        # Version pattern to find elements with version IDs
        version_pattern = re.compile(r"^(?:v\d+-\d+-\d+|\d+\.\d+\.\d+)$")

        # Find all elements with version-like IDs
        version_elements = soup.find_all(id=version_pattern)

        for elem in version_elements:
            anchor = elem.get("id")
            version = anchor.removeprefix("v").replace("-", ".")
            elem_text = elem.get_text(" ", strip=True)

            # Extract date from the element's text
            date_match = re.search(
                r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}",
                elem_text,
            )

            if date_match:
                date = parse_date(date_match.group())
            else:
                logger.warning(f"Could not find date for version {version}")
                raise ValueError(f"Missing publication date for version {version}")

            # Extract description from the prose/article content as HTML
            prose_elem = elem.select_one('[data-component-part="update-content"], .prose')
            if prose_elem:
                description = prose_elem.decode_contents()
            else:
                # Fallback: extract text with separator
                description = elem_text
                if date_match:
                    description = elem_text[date_match.end() :].strip()

            if not description:
                description = f"Version {version} release"

            # Create link with anchor
            link = f"{blog_url}#{anchor}"

            changelog_entries.append(
                {
                    "title": f"{title_prefix} {version}",
                    "version": version,
                    "guid": f"{legacy_url}#{version}#{version}",
                    "link": link,
                    "description": description,
                    "date": date,
                }
            )

        logger.info(f"Successfully parsed {len(changelog_entries)} changelog entries")
        return changelog_entries

    except Exception as e:
        logger.error(f"Error parsing HTML content: {e!s}")
        raise
