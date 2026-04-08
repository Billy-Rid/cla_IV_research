"""
Google Maps scraper for Nashville IV clinics.
Searches multiple terms, scrolls through all results, and extracts
business details from each listing panel.
"""

import asyncio
import random
import re
from pathlib import Path
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

SEARCH_TERMS = [
    ("IV therapy Nashville TN", "In-Person"),
    ("IV drip Nashville TN", "In-Person"),
    ("IV infusion clinic Nashville TN", "In-Person"),
    ("IV hydration Nashville TN", "In-Person"),
    ("mobile IV therapy Nashville TN", "Mobile"),
    ("mobile IV drip Nashville TN", "Mobile"),
    ("concierge IV Nashville TN", "Mobile"),
]

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

STEALTH_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
window.chrome = { runtime: {} };
"""


def _infer_service_type(name: str, hint: str) -> str:
    name_lower = name.lower()
    if any(w in name_lower for w in ("mobile", "concierge", "on-site", "on site", "travel")):
        return "Mobile"
    return hint


async def _scroll_results_panel(page) -> None:
    """Scroll the left-side results panel until no new results load."""
    # The results panel selector on Google Maps
    panel_selector = 'div[role="feed"]'
    try:
        panel = await page.query_selector(panel_selector)
        if not panel:
            return

        prev_count = 0
        for _ in range(15):  # max 15 scroll attempts
            await page.evaluate(
                """(panel) => { panel.scrollTop += 1200; }""",
                panel,
            )
            await asyncio.sleep(random.uniform(1.5, 2.5))

            # Count visible results to detect when we've hit the end
            items = await page.query_selector_all('div[role="feed"] > div > div[jsaction]')
            current_count = len(items)
            if current_count == prev_count:
                break
            prev_count = current_count

    except Exception:
        pass


async def _get_listing_links(page) -> list[str]:
    """Extract all business detail URLs from the results panel."""
    links = await page.evaluate("""
        () => {
            const anchors = document.querySelectorAll('a[href*="/maps/place/"]');
            const hrefs = new Set();
            anchors.forEach(a => {
                const href = a.href;
                if (href && href.includes('/maps/place/')) {
                    hrefs.add(href.split('?')[0]);
                }
            });
            return Array.from(hrefs);
        }
    """)
    return links


async def _extract_detail(page, url: str, service_hint: str, debug: bool = False) -> dict | None:
    """
    Navigate to a Google Maps business page and extract all available fields.
    Returns a dict or None if the page doesn't look like a valid business.
    """
    biz = {}
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=25000)
        await asyncio.sleep(random.uniform(2.0, 3.5))

        # Wait for the business name heading to appear
        await page.wait_for_selector('h1', timeout=8000)

        content = await page.content()

        if debug:
            debug_dir = Path("data/debug")
            debug_dir.mkdir(parents=True, exist_ok=True)
            safe = re.sub(r'[^a-z0-9]', '_', url.split('/place/')[-1][:40].lower())
            (debug_dir / f"gmaps_{safe}.html").write_text(content, encoding="utf-8")

        soup = BeautifulSoup(content, "lxml")

        # --- Business Name ---
        h1 = soup.find("h1")
        if not h1:
            return None
        biz["name"] = h1.get_text(strip=True)
        if not biz["name"]:
            return None

        biz["google_maps_url"] = url

        # Google Maps puts most info in aria-label attributes and button text.
        # We scan all text-bearing elements for known patterns.
        full_text = soup.get_text(" ", strip=True)

        # --- Address ---
        addr_btn = soup.find("button", attrs={"data-item-id": "address"})
        if addr_btn:
            biz["address"] = addr_btn.get_text(strip=True)
        else:
            # Fallback: look for a line that matches a Nashville address pattern
            addr_match = re.search(
                r"\d+\s+[\w\s]+(?:Ave|Blvd|Dr|Ln|Pike|Rd|St|Way)[,\s]+Nashville",
                full_text, re.I
            )
            if addr_match:
                biz["address"] = addr_match.group(0).strip()

        # --- Phone ---
        phone_btn = soup.find("button", attrs={"data-item-id": re.compile(r"phone")})
        if phone_btn:
            biz["phone"] = phone_btn.get_text(strip=True)
        else:
            phone_match = re.search(r"\(?\d{3}\)?[\s\-]\d{3}[\s\-]\d{4}", full_text)
            if phone_match:
                biz["phone"] = phone_match.group(0).strip()

        # --- Website ---
        website_link = soup.find("a", attrs={"data-item-id": "authority"})
        if website_link:
            biz["website"] = website_link.get("href", "")
        else:
            # Fallback: look for any external link button labeled "Website"
            ws_btn = soup.find("a", string=re.compile(r"^website$", re.I))
            if ws_btn:
                biz["website"] = ws_btn.get("href", "")

        # --- Rating ---
        rating_match = re.search(r"(\d\.\d)\s*\([\d,]+\s*review", full_text, re.I)
        if rating_match:
            biz["rating"] = float(rating_match.group(1))

        review_match = re.search(r"\(([\d,]+)\s*review", full_text, re.I)
        if review_match:
            biz["review_count"] = int(review_match.group(1).replace(",", ""))

        # --- Hours ---
        hours_btn = soup.find(attrs={"aria-label": re.compile(r"hour|open", re.I)})
        if hours_btn:
            biz["hours"] = hours_btn.get("aria-label", "")[:200]

        # --- Category / Business Type ---
        # Usually appears just below the name as a small label
        category_candidates = soup.find_all(
            attrs={"jsaction": re.compile(r"category|genre", re.I)}
        )
        if category_candidates:
            biz["category"] = category_candidates[0].get_text(strip=True)
        else:
            # Common IV clinic categories
            for cat in ("IV Hydration", "Medical Spa", "Health & Medical", "Wellness Center"):
                if cat.lower() in full_text.lower():
                    biz["category"] = cat
                    break

        biz["service_type"] = _infer_service_type(biz["name"], service_hint)

    except Exception as exc:
        if debug:
            print(f"    [debug] Error extracting {url}: {exc}")
        return None

    return biz


async def run_google_maps_scraper(fetch_details: bool = True, debug: bool = False) -> list:
    """
    Main entry point.
    Returns a deduplicated list of IV clinic dicts scraped from Google Maps.
    """
    all_clinics: list[dict] = []
    seen_names: set[str] = set()
    all_links: dict[str, str] = {}  # url -> service_hint

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=not debug,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=USER_AGENT,
            locale="en-US",
        )
        await context.add_init_script(STEALTH_SCRIPT)
        page = await context.new_page()

        # ── Phase 1: Collect all business URLs from search results ────────────
        for term, hint in SEARCH_TERMS:
            search_url = f"https://www.google.com/maps/search/{term.replace(' ', '+')}"
            print(f"  Searching Google Maps: '{term}'...")

            try:
                await page.goto(search_url, wait_until="domcontentloaded", timeout=25000)
                await asyncio.sleep(random.uniform(2.0, 3.5))

                # Dismiss any consent/cookie dialogs
                for btn_text in ("Accept all", "Reject all", "Accept", "I agree"):
                    try:
                        btn = page.get_by_role("button", name=btn_text)
                        if await btn.is_visible():
                            await btn.click()
                            await asyncio.sleep(1.0)
                            break
                    except Exception:
                        pass

                await _scroll_results_panel(page)
                links = await _get_listing_links(page)

                new_links = 0
                for link in links:
                    if link not in all_links:
                        all_links[link] = hint
                        new_links += 1

                print(f"    +{new_links} new links (total: {len(all_links)})")

            except Exception as exc:
                print(f"    Warning: failed search '{term}': {exc}")

            await asyncio.sleep(random.uniform(3.0, 5.0))

        # ── Phase 2: Visit each business page for full details ────────────────
        if fetch_details and all_links:
            print(f"\n  Extracting details for {len(all_links)} businesses...")
            for i, (url, hint) in enumerate(all_links.items()):
                print(f"  [{i+1}/{len(all_links)}] {url.split('/place/')[-1].split('/')[0][:50]}")

                biz = await _extract_detail(page, url, hint, debug=debug)

                if biz:
                    key = biz.get("name", "").lower().strip()
                    if key and key not in seen_names:
                        seen_names.add(key)
                        all_clinics.append(biz)
                        print(f"    -> {biz['name']}")

                await asyncio.sleep(random.uniform(2.5, 4.0))

        elif not fetch_details:
            # Return stubs with just the URL and hint when details are skipped
            for url, hint in all_links.items():
                all_clinics.append({"google_maps_url": url, "service_type": hint})

        await browser.close()

    return all_clinics