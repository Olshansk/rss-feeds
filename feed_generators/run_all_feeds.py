import argparse
import os
import subprocess
import logging
import sys

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def uses_selenium(script_path):
    """Check if a generator script uses Selenium (undetected_chromedriver).

    Reads the first 3KB of the file to check for selenium imports.
    This is used to split generators into hourly (requests) and daily (selenium) runs.
    """
    try:
        with open(script_path, "r") as f:
            head = f.read(3072)
        return "undetected_chromedriver" in head
    except Exception:
        return False


def run_all_feeds(skip_selenium=False, selenium_only=False):
    """Run all Python scripts in the feed_generators directory.

    Args:
        skip_selenium: If True, skip generators that use Selenium/undetected_chromedriver.
                      Used by the hourly requests workflow to run only lightweight generators.
        selenium_only: If True, run ONLY generators that use Selenium.
                      Used by the hourly Selenium workflow to run only heavy generators.

    Returns:
        int: Exit code (0 for success, 1 if any script failed)
    """
    feed_generators_dir = os.path.dirname(os.path.abspath(__file__))
    skip_scripts = ["utils.py", "test_feed.py", "validate_feeds.py"]
    failed_scripts = []
    successful_scripts = []
    skipped_scripts = []

    for filename in sorted(os.listdir(feed_generators_dir)):
        if filename.endswith(".py") and filename != os.path.basename(__file__):
            if filename in skip_scripts:
                logger.info(f"Skipping script: {filename}")
                continue

            script_path = os.path.join(feed_generators_dir, filename)
            is_selenium = uses_selenium(script_path)

            if skip_selenium and is_selenium:
                logger.info(f"Skipping Selenium generator: {filename}")
                skipped_scripts.append(filename)
                continue

            if selenium_only and not is_selenium:
                logger.info(f"Skipping non-Selenium generator: {filename}")
                skipped_scripts.append(filename)
                continue

            logger.info(f"Running script: {script_path}")
            result = subprocess.run(["uv", "run", script_path], capture_output=True, text=True)
            if result.returncode == 0:
                logger.info(f"Successfully ran script: {script_path}")
                successful_scripts.append(filename)
            else:
                logger.error(f"Error running script: {script_path}\n{result.stderr}")
                failed_scripts.append(filename)

    # Summary
    logger.info(f"\n{'='*60}")
    logger.info(f"Feed Generation Summary:")
    logger.info(f"  Successful: {len(successful_scripts)}")
    logger.info(f"  Failed: {len(failed_scripts)}")
    logger.info(f"  Skipped: {len(skipped_scripts)}")

    if successful_scripts:
        logger.info(f"\nSuccessful feeds:")
        for script in successful_scripts:
            logger.info(f"  ✓ {script}")

    if failed_scripts:
        logger.error(f"\nFailed feeds:")
        for script in failed_scripts:
            logger.error(f"  ✗ {script}")
        logger.error(f"\nERROR: {len(failed_scripts)} feed(s) failed to generate")
        return 1

    if skipped_scripts:
        logger.info(f"\nSkipped feeds:")
        for script in skipped_scripts:
            logger.info(f"  ○ {script}")

    logger.info(f"{'='*60}\n")
    return 0

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run RSS feed generators")
    parser.add_argument(
        "--skip-selenium",
        action="store_true",
        help="Skip generators that use Selenium (for hourly lightweight runs)",
    )
    parser.add_argument(
        "--selenium-only",
        action="store_true",
        help="Run only generators that use Selenium (for daily heavy runs)",
    )
    args = parser.parse_args()

    if args.skip_selenium and args.selenium_only:
        logger.error("Cannot use both --skip-selenium and --selenium-only")
        sys.exit(1)

    exit_code = run_all_feeds(
        skip_selenium=args.skip_selenium,
        selenium_only=args.selenium_only,
    )
    sys.exit(exit_code)
