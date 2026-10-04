"""Strict publication-date parsing shared by static and dynamic sources."""

import re
from datetime import UTC, datetime


def parse_date(text: str) -> datetime:
    """Parse ISO or English publication dates without inventing a current date.

    How:
    1. Normalize September abbreviations and punctuation.
    2. Try ISO timestamps, then explicit day/month formats.
    3. Require a complete date and return a timezone-aware value.
    """
    text = re.sub(r"\bSept\.?", "Sep", text.strip(), flags=re.IGNORECASE)
    try:
        date = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return date if date.tzinfo else date.replace(tzinfo=UTC)
    except ValueError:
        pass
    text = text.replace(".", "").title()
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%d %B %Y", "%d %b %Y", "%B %d %Y", "%b %d %Y"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    raise ValueError(f"Unrecognized publication date: {text!r}")
