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

    How:
    1. Configure browser options for headless rendering.
    2. Detect the installed Chrome version to avoid driver mismatches.
    3. Start Chrome with the optional RSS_CHROMEDRIVER override.
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


def fetch_rendered(url, article_selector, *, button_xpath=None, max_clicks=0, configure=None):
    """Fetch a dynamic listing, optionally expanding it, and always close Chrome.

    How:
    1. Configure the browser and wait for actual article elements.
    2. Click the expansion control while present, requiring article-count growth.
    3. Return the rendered document and close the browser even after a failure.
    """
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    driver = setup_selenium_driver()
    try:
        driver.set_page_load_timeout(45)
        if configure:
            configure(driver)
        driver.get(url)
        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.CSS_SELECTOR, article_selector)))
        for _ in range(max_clicks):
            buttons = driver.find_elements(By.XPATH, button_xpath)
            if not buttons or not buttons[0].is_displayed() or not buttons[0].is_enabled():
                break
            count = len(driver.find_elements(By.CSS_SELECTOR, article_selector))
            driver.execute_script("arguments[0].click();", buttons[0])
            WebDriverWait(driver, 20).until(
                lambda current, previous=count: len(current.find_elements(By.CSS_SELECTOR, article_selector)) > previous
            )
        return driver.page_source
    finally:
        driver.quit()
