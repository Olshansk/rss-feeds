import argparse
import logging
import os
import subprocess
import sys

from models import FeedConfig, FeedType, load_feed_registry

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def run_feed(feed_name: str, config: FeedConfig, full: bool = False) -> bool:
    """Run a single feed generator.

    Args:
        feed_name: Registry name of the feed.
        config: Validated feed configuration.
        full: If True, pass --full flag to the generator.

    Returns:
        True if the generator succeeded, False otherwise.
    """
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), config.script)
    cmd = ["uv", "run", script_path]
    if full:
        cmd.append("--full")

    logger.info(f"Running {feed_name}: {script_path}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        logger.info(f"Successfully ran: {feed_name}")
        return True
    else:
        logger.error(f"Error running {feed_name}:\n{result.stderr}")
        return False


def run_all_feeds(
    skip_selenium: bool = False,
    selenium_only: bool = False,
    feed: str | None = None,
    full: bool = False,
) -> int:
    """Run feed generators from the registry.

    Args:
        skip_selenium: Skip Selenium-based generators (for hourly requests workflow).
        selenium_only: Run only Selenium-based generators (for hourly Selenium workflow).
        feed: Run a single feed by name. Overrides skip_selenium/selenium_only.
        full: Pass --full flag to generators (full reset instead of incremental).

    Returns:
        Exit code (0 for success, 1 if any feed failed).
    """
    registry = load_feed_registry()

    # Single feed mode
    if feed:
        if feed not in registry:
            logger.error(f"Feed '{feed}' not found in registry. Available: {', '.join(sorted(registry))}")
            return 1
        config = registry[feed]
        if not config.enabled:
            logger.warning(f"Feed '{feed}' is disabled in feeds.yaml")
            return 1
        ok = run_feed(feed, config, full=full)
        return 0 if ok else 1

    # Multi-feed mode
    failed_scripts = []
    successful_scripts = []
    skipped_scripts = []

    for name, config in sorted(registry.items()):
        if not config.enabled:
            logger.info(f"Skipping disabled feed: {name}")
            skipped_scripts.append(name)
            continue

        is_selenium = config.type == FeedType.SELENIUM

        if skip_selenium and is_selenium:
            logger.info(f"Skipping Selenium generator: {name}")
            skipped_scripts.append(name)
            continue

        if selenium_only and not is_selenium:
            logger.info(f"Skipping non-Selenium generator: {name}")
            skipped_scripts.append(name)
            continue

        ok = run_feed(name, config, full=full)
        if ok:
            successful_scripts.append(name)
        else:
            failed_scripts.append(name)

    # Summary
    logger.info(f"\n{'=' * 60}")
    logger.info("Feed Generation Summary:")
    logger.info(f"  Successful: {len(successful_scripts)}")
    logger.info(f"  Failed: {len(failed_scripts)}")
    logger.info(f"  Skipped: {len(skipped_scripts)}")

    if successful_scripts:
        logger.info("\nSuccessful feeds:")
        for name in successful_scripts:
            logger.info(f"  ✓ {name}")

    if failed_scripts:
        logger.error("\nFailed feeds:")
        for name in failed_scripts:
            logger.error(f"  ✗ {name}")
        logger.error(f"\nERROR: {len(failed_scripts)} feed(s) failed to generate")
        return 1

    if skipped_scripts:
        logger.info("\nSkipped feeds:")
        for name in skipped_scripts:
            logger.info(f"  ○ {name}")

    logger.info(f"{'=' * 60}\n")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run RSS feed generators")
    parser.add_argument(
        "--skip-selenium",
        action="store_true",
        help="Skip Selenium-based generators (for hourly requests workflow)",
    )
    parser.add_argument(
        "--selenium-only",
        action="store_true",
        help="Run only Selenium-based generators (for hourly Selenium workflow)",
    )
    parser.add_argument(
        "--feed",
        type=str,
        help="Run a single feed by name (e.g., --feed=ollama)",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Pass --full to generators (full reset instead of incremental)",
    )
    args = parser.parse_args()

    if args.skip_selenium and args.selenium_only:
        logger.error("Cannot use both --skip-selenium and --selenium-only")
        sys.exit(1)

    exit_code = run_all_feeds(
        skip_selenium=args.skip_selenium,
        selenium_only=args.selenium_only,
        feed=args.feed,
        full=args.full,
    )
    sys.exit(exit_code)
