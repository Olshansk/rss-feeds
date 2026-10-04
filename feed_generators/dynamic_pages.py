"""Browser setup for JavaScript-rendered listings."""

import logging
import os
import re
import subprocess

from static_pages import DEFAULT_USER_AGENT

logger = logging.getLogger(__name__)


def get_chrome_major_version() -> int | None:
    """Detect the installed Chrome major version.

    Returns the major version number (e.g., 146) or None if detection fails.
    This is needed because undetected_chromedriver auto-downloads the latest
    chromedriver, which may not match the installed Chrome version.
    """
    chrome_paths = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "google-chrome",
        "google-chrome-stable",
    ]
    for path in chrome_paths:
        try:
            result = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=5)
            match = re.search(r"(\d+)\.", result.stdout)
            if match:
                version = int(match.group(1))
                logger.info(f"Detected Chrome major version: {version}")
                return version
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    logger.warning("Could not detect Chrome version, using undetected_chromedriver default")
    return None


def setup_selenium_driver():
    """Set up a headless Selenium WebDriver with undetected-chromedriver.

    Automatically detects the installed Chrome version to avoid
    chromedriver version mismatches.
    """
    import undetected_chromedriver as uc

    options = uc.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(f"--user-agent={DEFAULT_USER_AGENT}")
    version = get_chrome_major_version()
    driver_path = os.environ.get("RSS_CHROMEDRIVER")
    return uc.Chrome(options=options, version_main=version, driver_executable_path=driver_path)
