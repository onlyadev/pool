#!/usr/bin/env python3
"""
Yellow Pages Scraper - TEST VERSION
Scrapes only 50 results total for testing purposes.
Uses playwright-stealth and fresh browser contexts per state.
"""

import csv
import logging
import random
import time
from urllib.parse import quote

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from playwright_stealth import Stealth

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
SEARCH_TERM = "pool cleaning and maintenance"
STATES = ["FL", "CA"]  # Just 2 states for this test
BASE_URL = "https://www.yellowpages.com/search"
MAX_RESULTS = 300  # ~5 pages per state to test browser rotation
MAX_PAGES_PER_STATE = 5  # Limit pages per state

# Expected results per state (for retry logic - retry if below expected count)
EXPECTED_RESULTS = {
    "FL": 2800,
    "CA": 2800,
    "TX": 2800,
    "AZ": 2700,
    "NY": 1400,
    "NJ": 1400,
    "PA": 1200,
    "OH": 1100,
    "MI": 600,
    "MA": 500,
}

# Varied user agents and browser configurations
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
]

VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1366, "height": 768},
    {"width": 1536, "height": 864},
    {"width": 1440, "height": 900},
    {"width": 1280, "height": 720},
]

TIMEZONES = [
    "America/New_York",
    "America/Chicago",
    "America/Denver",
    "America/Los_Angeles",
    "America/Phoenix",
]

LOCALES = ["en-US", "en-GB", "en-CA"]


def get_random_browser_config():
    """Generate random browser configuration to vary fingerprint."""
    return {
        "user_agent": random.choice(USER_AGENTS),
        "viewport": random.choice(VIEWPORTS),
        "timezone_id": random.choice(TIMEZONES),
        "locale": random.choice(LOCALES),
    }


def get_page_url(state: str, page: int = 1) -> str:
    """Construct the URL for a specific state and page number."""
    encoded_search = quote(SEARCH_TERM)
    if page == 1:
        return f"{BASE_URL}?search_terms={encoded_search}&geo_location_terms={state}"
    return f"{BASE_URL}?search_terms={encoded_search}&geo_location_terms={state}&page={page}"


def extract_business_info(result, state: str) -> dict:
    """Extract business information from a search result element."""
    business = {
        "name": "N/A",
        "website": "N/A",
        "phone": "N/A",
        "categories": "N/A",
        "state": state,
        "moved": False
    }

    name_elem = result.find("a", class_="business-name")
    if name_elem:
        business["name"] = name_elem.get_text(strip=True)

    website_elem = result.find("a", class_="track-visit-website")
    if website_elem and website_elem.get("href"):
        business["website"] = website_elem.get("href")

    phone_elem = result.find("div", class_="phones")
    if phone_elem:
        business["phone"] = phone_elem.get_text(strip=True)

    categories_elem = result.find("div", class_="categories")
    if categories_elem:
        category_links = categories_elem.find_all("a")
        if category_links:
            categories = [cat.get_text(strip=True) for cat in category_links]
            business["categories"] = ", ".join(categories)
        else:
            business["categories"] = categories_elem.get_text(strip=True)

    moved_elem = result.find("span", class_="MOVED")
    if moved_elem:
        business["moved"] = True

    return business


def human_like_delay(min_sec=1.0, max_sec=3.0):
    """Add human-like random delay."""
    delay = random.uniform(min_sec, max_sec)
    time.sleep(delay)
    return delay


def scrape_page(page, state: str, page_num: int, retry_attempt: int = 0) -> tuple[list[dict], bool, bool]:
    """Scrape a single page of results.

    Returns: (businesses, has_next, success)
    """
    url = get_page_url(state, page_num)
    logger.info(f"Scraping {state} - Page {page_num}: {url}" + (f" (retry {retry_attempt})" if retry_attempt > 0 else ""))

    try:
        # Navigate with random delay before
        human_like_delay(0.5, 1.5)

        page.goto(url, wait_until="domcontentloaded", timeout=30000)

        # Wait for results with longer timeout
        page.wait_for_selector(".search-results", timeout=15000)

        # Human-like delay after page load
        human_like_delay(2.0, 4.0)

        # Simulate more natural scrolling behavior
        page.evaluate("window.scrollBy(0, 300)")
        human_like_delay(0.5, 1.2)
        page.evaluate("window.scrollBy(0, 400)")
        human_like_delay(0.3, 0.8)
        page.evaluate("window.scrollBy(0, 200)")

    except PlaywrightTimeout:
        logger.error(f"Timeout loading {url}")
        return [], False, False  # success=False indicates timeout
    except Exception as e:
        logger.error(f"Failed to load {url}: {e}")
        return [], False, False

    soup = BeautifulSoup(page.content(), "html.parser")
    results = soup.find_all("div", class_="result")

    if not results:
        logger.warning(f"No results found on {state} - Page {page_num}")
        return [], False, True  # success=True (page loaded, just no results)

    businesses = []
    for result in results:
        result_classes = result.get("class", [])
        if "ad" in result_classes or "advertisement" in result_classes:
            continue

        business = extract_business_info(result, state)
        if business["name"] != "N/A":
            businesses.append(business)

    has_next = False
    pagination = soup.find("div", class_="pagination")
    if pagination:
        next_link = pagination.find("a", class_="next")
        if next_link and "href" in next_link.attrs:
            has_next = True

    logger.info(f"Found {len(businesses)} businesses on page {page_num}")
    return businesses, has_next, True  # success=True


def create_fresh_browser(playwright):
    """Create a new browser instance with fresh context and varied fingerprint."""
    config = get_random_browser_config()

    browser = playwright.chromium.launch(
        headless=False,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-web-security",
            "--disable-features=IsolateOrigins,site-per-process",
            "--start-maximized",
        ]
    )

    context = browser.new_context(
        viewport=config["viewport"],
        user_agent=config["user_agent"],
        locale=config["locale"],
        timezone_id=config["timezone_id"],
        java_script_enabled=True,
        has_touch=False,
        is_mobile=False,
        device_scale_factor=random.choice([1, 1.25, 1.5, 2]),
        color_scheme=random.choice(["light", "dark", "no-preference"]),
    )

    page = context.new_page()

    # Apply stealth
    stealth = Stealth()
    stealth.apply_stealth_sync(page)

    return browser, context, page, config


def scrape_state_with_fresh_context(playwright, state: str, remaining_needed: int) -> list[dict]:
    """Scrape a state, rotating browser context every 2-4 pages with retry logic."""
    all_businesses = []
    page_num = 1
    pages_until_refresh = random.randint(2, 4)
    pages_in_current_context = 0
    max_retries = 2
    retry_delay_range = (20.0, 30.0)
    expected_for_state = EXPECTED_RESULTS.get(state, 500)  # Use per-state expected count

    browser, context, page, config = create_fresh_browser(playwright)
    logger.info(f"Using config for {state}: UA={config['user_agent'][:50]}..., viewport={config['viewport']}")
    logger.info(f"Will refresh browser after {pages_until_refresh} pages")

    try:
        while len(all_businesses) < remaining_needed and page_num <= MAX_PAGES_PER_STATE:
            # Try to scrape the page with retry logic
            businesses, has_next, success = scrape_page(page, state, page_num)

            # Handle timeout OR empty results with retries (only if below expected count for this state)
            needs_retry = (not success or not businesses) and len(all_businesses) < expected_for_state
            if needs_retry:
                reason = "Timeout" if not success else "No results"
                for retry in range(1, max_retries + 1):
                    logger.warning(f"{reason} on {state} page {page_num}. Retry {retry}/{max_retries} with fresh browser...")

                    # Close current browser and create fresh one
                    context.close()
                    browser.close()

                    # Long delay before retry
                    delay = human_like_delay(*retry_delay_range)
                    logger.info(f"Waiting {delay:.1f}s before retry...")

                    browser, context, page, config = create_fresh_browser(playwright)
                    logger.info(f"Retry config: UA={config['user_agent'][:50]}..., viewport={config['viewport']}")

                    # Try again
                    businesses, has_next, success = scrape_page(page, state, page_num, retry_attempt=retry)

                    if success:
                        logger.info(f"Retry {retry} succeeded!")
                        pages_until_refresh = random.randint(2, 4)
                        pages_in_current_context = 0
                        break

                if not success or not businesses:
                    logger.error(f"All {max_retries} retries failed for {state} page {page_num}. Moving on.")
                    break
            elif not success or not businesses:
                logger.info(f"Issue on {state} page {page_num}, but already have {len(all_businesses)}/{expected_for_state} expected results. Stopping state.")
                break

            pages_in_current_context += 1

            if not businesses:
                break

            # Only take what we need
            for biz in businesses:
                if len(all_businesses) >= remaining_needed:
                    break
                all_businesses.append(biz)

            if len(all_businesses) >= remaining_needed:
                break

            if not has_next:
                break

            page_num += 1

            # Check if we need to refresh browser context
            if pages_in_current_context >= pages_until_refresh:
                logger.info(f"Refreshing browser context after {pages_in_current_context} pages")
                context.close()
                browser.close()

                # Delay before new browser
                delay = human_like_delay(3.0, 6.0)
                logger.info(f"Waiting {delay:.1f}s before new browser context...")

                browser, context, page, config = create_fresh_browser(playwright)
                logger.info(f"New config: UA={config['user_agent'][:50]}..., viewport={config['viewport']}")
                pages_until_refresh = random.randint(2, 4)
                pages_in_current_context = 0
                logger.info(f"Will refresh browser after {pages_until_refresh} pages")
            else:
                # Random delay between pages (3-10 seconds)
                delay = human_like_delay(3.0, 10.0)
                logger.info(f"Waiting {delay:.1f}s before next page")

    finally:
        context.close()
        browser.close()
        logger.info(f"Closed browser context for {state}")

    return all_businesses


def main():
    """Main entry point - TEST VERSION with 50 result limit."""
    logger.info("Starting Yellow Pages scraper - TEST MODE (50 results max)")
    logger.info(f"Search term: {SEARCH_TERM}")
    logger.info("Using playwright-stealth with fresh browser per state")

    all_businesses = []

    with sync_playwright() as p:
        for state in STATES:
            if len(all_businesses) >= MAX_RESULTS:
                logger.info(f"Reached {MAX_RESULTS} results limit, stopping")
                break

            remaining = MAX_RESULTS - len(all_businesses)
            logger.info(f"\n{'='*50}")
            logger.info(f"Processing state: {state} (need {remaining} more results)")
            logger.info(f"{'='*50}")

            try:
                businesses = scrape_state_with_fresh_context(p, state, remaining)

                if businesses:
                    for biz in businesses:
                        biz["state"] = state
                    all_businesses.extend(businesses)
                    logger.info(f"Got {len(businesses)} from {state}, total now: {len(all_businesses)}")
                else:
                    logger.warning(f"No businesses found for {state}")

            except Exception as e:
                logger.error(f"Error processing {state}: {e}")

            # Longer delay between states (new browser context)
            if len(all_businesses) < MAX_RESULTS and state != STATES[-1]:
                delay = human_like_delay(3.0, 6.0)
                logger.info(f"Waiting {delay:.1f}s before next state...")

    # Save all results to a single test CSV
    if all_businesses:
        filename = "yellowpages_pool_services_TEST.csv"
        fieldnames = ["name", "website", "phone", "categories", "state", "moved"]

        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_businesses)

        logger.info(f"\nSaved {len(all_businesses)} businesses to {filename}")

        # Print summary by state
        state_counts = {}
        for biz in all_businesses:
            state_counts[biz["state"]] = state_counts.get(biz["state"], 0) + 1
        logger.info("Results by state:")
        for state, count in state_counts.items():
            logger.info(f"  {state}: {count}")
    else:
        logger.warning("No businesses found")


if __name__ == "__main__":
    main()
