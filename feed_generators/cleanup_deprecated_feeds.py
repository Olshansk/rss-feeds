"""Delete RSS feed XML files whose deprecation notice is older than the threshold.

A feed is considered "retired" once ``deprecate_feed.py`` has injected a
sunset ``<item>`` (GUID prefix ``deprecation-notice-``) and the human has
removed the generator, registry entry, Make target, and README row. This
script handles the final step: deleting the tombstone XML after enough time
has passed that existing subscribers have almost certainly seen the notice.

Default mode is dry-run: prints a punch list of eligible files. Use
``--apply`` to actually delete. The GitHub Actions workflow
``cleanup_deprecated_feeds.yml`` runs this with ``--apply`` on a monthly cron.
"""

import argparse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path

import pytz

from utils import get_feeds_dir, setup_logging

logger = setup_logging()

DEPRECATION_GUID_PREFIX = "deprecation-notice-"
RFC822_FORMAT = "%a, %d %b %Y %H:%M:%S %z"
DEFAULT_THRESHOLD_DAYS = 90


def find_deprecation_notice(feed_file: Path) -> datetime | None:
    """Return the pubDate of the deprecation <item> in ``feed_file``, or None."""
    try:
        tree = ET.parse(feed_file)
    except ET.ParseError as e:
        logger.warning(f"Could not parse {feed_file}: {e}")
        return None

    channel = tree.getroot().find("channel")
    if channel is None:
        return None

    # A feed should only ever carry one tombstone, but keep looking if the
    # first match is malformed rather than failing the whole file.
    for item in channel.findall("item"):
        guid = item.find("guid")
        if guid is None or not guid.text or not guid.text.startswith(DEPRECATION_GUID_PREFIX):
            continue

        pub_date_elem = item.find("pubDate")
        if pub_date_elem is None or not pub_date_elem.text:
            logger.warning(f"Deprecation notice in {feed_file} has no pubDate; skipping item")
            continue
        try:
            return datetime.strptime(pub_date_elem.text, RFC822_FORMAT)
        except ValueError as e:
            logger.warning(f"Could not parse pubDate in {feed_file} ({e}); skipping item")
            continue
    return None


def find_eligible_feeds(threshold_days: int) -> list[tuple[Path, int]]:
    """Return (path, age_days) for every feed XML whose notice is older than threshold_days."""
    now = datetime.now(pytz.UTC)
    cutoff = now - timedelta(days=threshold_days)
    eligible: list[tuple[Path, int]] = []
    for feed_file in sorted(get_feeds_dir().glob("feed_*.xml")):
        pub_date = find_deprecation_notice(feed_file)
        if pub_date is None:
            continue
        age_days = (now - pub_date).days
        if pub_date < cutoff:
            eligible.append((feed_file, age_days))
    return eligible


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--threshold-days",
        type=int,
        default=DEFAULT_THRESHOLD_DAYS,
        help=f"Age in days after which a deprecated feed XML is deleted (default: {DEFAULT_THRESHOLD_DAYS})",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually delete eligible files (default is dry-run)",
    )
    args = parser.parse_args()

    eligible = find_eligible_feeds(args.threshold_days)

    if not eligible:
        logger.info(f"No deprecated feeds older than {args.threshold_days} days")
        return 0

    logger.info(f"Found {len(eligible)} deprecated feed(s) older than {args.threshold_days} days:")
    for feed_file, age_days in eligible:
        logger.info(f"  {feed_file.name} (notice is {age_days} days old)")

    if args.apply:
        for feed_file, _ in eligible:
            feed_file.unlink()
            logger.info(f"Deleted {feed_file}")
    else:
        logger.info("Dry run. Re-run with --apply to delete these files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
