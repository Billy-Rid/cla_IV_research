"""
Yelp scraper for Nashville IV clinics.
Searches multiple terms to capture both in-person and mobile IV providers.
Uses Playwright to handle JavaScript-rendered pages.
"""

import asyncio
import random
import re
from pathlib import Path
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

SEARCH_TERMS = [
    ("IV therapy", "In-Person"),
    ("IV drip", "In-Person"),
    ("IV infusion", "In-Person"),
    ("IV hydration", "In-Person"),
    ("mobile IV therapy", "Mobile"),
    ("mobile IV drip", "Mobile"),
    ("mobile IV Nashville", "Mobile"),
]

YELP_SEARCH_URL = "https://www.yelp.com/search?find_desc={desc}&find_loc=Nashville%2C+TN"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

# Injected into every page to mask Playwright's automation fingerprint
STEALTH_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
window.chrome = { runtime: {} };
"""


def _infer_service_type(name: str, categories: str, hint: str) -> str:
    combined = (name + " " + categories).lower()
    if "mobile" in combined or "concierge" in combined or "on-site" in combined:
        return "Mobile"
    return hint


async def _scrape_business_detail(page, url: str) -> dict:
    extra = {}
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        await asyncio.sleep(random.uniform(1.5, 2.5))

        soup = BeautifulSoup(await page.content(), "lxml")

        phone_tag = soup.find("a", href=re.compile(r"^tel:"))
        if phone_tag:
            extra["phone"] = phone_tag.get_text(strip=True)

        biz_website = soup.find("a", href=re.compile(r"biz_redir"))
        if biz_website:
            extra["website"] = biz_website.get_text(strip=True)

        hours_section = soup.find(string=re.compile(r"Mon|Tue|Wed|Thu|Fri|Sat|Sun"))
        if hours_section:
            parent = hours_section.find_parent("table") or hours_section.find_parent("ul")
            if parent:
                extra["hours"] = parent.get_text(" ", strip=True)[:200]

        about = soup.find("section", attrs={"aria-label": re.compile(r"about", re.I)})
        if about:
            extra["about_snippet"] = about.get_text(" ", strip=True)[:300]

    except Exception as exc:
        extra["detail_error"] = str(exc)

    return extra


async def _scrape_search_page(page, search_term: str, service_hint: str, debug: bool = False) -> list:
    url = YELP_SEARCH_URL.format(desc=search_term.replace(" ", "+"))
    results = []

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=25000)

        # Simulate a human scrolling down before reading the page
        await asyncio.sleep(random.uniform(1.5, 2.5))
        await page.mouse.move(random.randint(300, 900), random.randint(200, 600))
        await page.evaluate("window.scrollBy(0, 400)")
        await asyncio.sleep(random.uniform(1.5, 2.5))
        await page.evaluate("window.scrollBy(0, 400)")
        await asyncio.sleep(random.uniform(1.0, 2.0))

        content = await page.content()

        # In debug mode, save the raw HTML so you can inspect what Yelp returned
        if debug:
            debug_dir = Path("data/debug")
            debug_dir.mkdir(parents=True, exist_ok=True)
            safe_name = search_term.replace(" ", "_")
            (debug_dir / f"yelp_{safe_name}.html").write_text(content, encoding="utf-8")
            print(f"    [debug] HTML saved to data/debug/yelp_{safe_name}.html")

        soup = BeautifulSoup(content, "lxml")

        candidate_links = soup.find_all(
            "a",
            href=re.compile(r"^/biz/"),
            string=True,
        )

        seen_hrefs = set()
        for link in candidate_links:
            href = link.get("href", "")
            if any(x in href for x in ("?", "review", "photo", "map")):
                continue
            if href in seen_hrefs:
                continue
            seen_hrefs.add(href)

            biz = {
                "name": link.get_text(strip=True),
                "yelp_url": "https://www.yelp.com" + href,
                "source_search_term": search_term,
            }

            container = link
            for _ in range(6):
                container = container.parent
                if container is None:
                    break
                if container.name in ("li", "div", "article"):
                    break

            if container:
                text_blob = container.get_text(" ", strip=True)

                rating_match = re.search(r"(\d\.\d)\s*star", text_blob, re.I)
                if rating_match:
                    biz["rating"] = float(rating_match.group(1))

                review_match = re.search(r"(\d+)\s+review", text_blob, re.I)
                if review_match:
                    biz["review_count"] = int(review_match.group(1))

                addr_tag = container.find("address") or container.find(
                    attrs={"class": re.compile(r"address|location", re.I)}
                )
                if addr_tag:
                    biz["address_snippet"] = addr_tag.get_text(strip=True)

                cat_links = container.find_all("a", href=re.compile(r"/c/"))
                if cat_links:
                    biz["categories"] = ", ".join(
                        c.get_text(strip=True) for c in cat_links
                    )

            biz["service_type"] = _infer_service_type(
                biz.get("name", ""),
                biz.get("categories", ""),
                service_hint,
            )

            results.append(biz)

    except Exception as exc:
        print(f"    Warning: error scraping '{search_term}': {exc}")

    return results


async def run_yelp_scraper(fetch_details: bool = True, debug: bool = False) -> list:
    """
    Main entry point.
    debug=True  → shows the browser window + saves raw HTML for inspection.
    fetch_details=False → skips per-clinic detail page visits (faster).
    """
    all_clinics: list[dict] = []
    seen_names: set[str] = set()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=not debug,  # visible window in debug mode
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=USER_AGENT,
            locale="en-US",
        )

        # Mask automation fingerprint on every page load
        await context.add_init_script(STEALTH_SCRIPT)

        page = await context.new_page()

        # Warm up: visit Yelp homepage first so we don't land cold on a search
        await page.goto("https://www.yelp.com", wait_until="domcontentloaded", timeout=20000)
        await asyncio.sleep(random.uniform(2.0, 3.5))

        for term, hint in SEARCH_TERMS:
            print(f"  Searching Yelp: '{term}'...")
            results = await _scrape_search_page(page, term, hint, debug=debug)

            new_count = 0
            for biz in results:
                key = biz.get("name", "").lower().strip()
                if key and key not in seen_names:
                    seen_names.add(key)
                    all_clinics.append(biz)
                    new_count += 1

            print(f"    +{new_count} new (total: {len(all_clinics)})")
            await asyncio.sleep(random.uniform(4.0, 7.0))

        if fetch_details and all_clinics:
            print(f"\n  Fetching detail pages for {len(all_clinics)} clinics...")
            for i, clinic in enumerate(all_clinics):
                yelp_url = clinic.get("yelp_url", "")
                if not yelp_url:
                    continue
                print(f"  [{i+1}/{len(all_clinics)}] {clinic.get('name', '')}")
                details = await _scrape_business_detail(page, yelp_url)
                clinic.update(details)
                await asyncio.sleep(random.uniform(2.0, 3.5))

        await browser.close()

    return all_clinics