"""
Nashville IV Clinic Competitor Research Tool
============================================
Scrapes Google Maps for every in-person and mobile IV clinic in Nashville,
then enriches each result with Tennessee Secretary of State business
registry data (entity type, status, ownership, registered agent).

Output: data/nashville_iv_clinics.csv
"""

import asyncio
import sys
from pathlib import Path

import pandas as pd

from scrapers.google_maps_scraper import run_google_maps_scraper
from scrapers.tn_sos import enrich_with_sos

OUTPUT_DIR = Path("data")
OUTPUT_FILE = OUTPUT_DIR / "nashville_iv_clinics.csv"

COLUMN_ORDER = [
    "name",
    "service_type",
    "address",
    "phone",
    "website",
    "rating",
    "review_count",
    "category",
    "hours",
    # TN SOS — business structure
    "registered_name",
    "entity_type",
    "sos_status",
    "sos_id",
    "date_formed",
    "registered_agent",
    "principal_office",
    "owners_officers",
    # Extra
    "google_maps_url",
    "source_search_term",
]


def _reorder_columns(df: pd.DataFrame) -> pd.DataFrame:
    existing = [c for c in COLUMN_ORDER if c in df.columns]
    extras = [c for c in df.columns if c not in COLUMN_ORDER]
    return df[existing + extras]


def _print_summary(df: pd.DataFrame) -> None:
    print("\n" + "=" * 60)
    print(f"  Total clinics found : {len(df)}")

    if "service_type" in df.columns:
        for stype, count in df["service_type"].value_counts().items():
            print(f"  {stype:<20}: {count}")

    if "entity_type" in df.columns:
        print(f"\n  Business entity breakdown (TN SOS):")
        for etype, count in df["entity_type"].value_counts().items():
            if etype:
                print(f"    {etype:<30}: {count}")

    if "sos_status" in df.columns:
        not_found = (df["sos_status"] == "Not Found in TN SOS").sum()
        if not_found:
            print(f"\n  Note: {not_found} clinic(s) had no TN SOS match.")
            print("  They may operate under a DBA or be unregistered.")

    print("=" * 60)


def run(skip_details: bool = False, skip_sos: bool = False, debug: bool = False) -> pd.DataFrame:
    """
    Main pipeline.

    Flags:
        --fast      Skip per-clinic detail page visits (quicker, less data)
        --skip-sos  Skip the TN Secretary of State ownership lookup
        --debug     Show the browser window + save raw HTML for inspection
    """
    OUTPUT_DIR.mkdir(exist_ok=True)

    print("\n=== Nashville IV Clinic Competitor Research Tool ===\n")

    # ── Step 1: Google Maps scraping ──────────────────────────────────────────
    print("[1/2] Scraping Google Maps for Nashville IV clinics...")
    if debug:
        print("      [debug mode: browser window will be visible]\n")

    clinics = asyncio.run(
        run_google_maps_scraper(fetch_details=not skip_details, debug=debug)
    )
    print(f"\n  Done. {len(clinics)} unique clinics found.\n")

    if not clinics:
        print("  No clinics found.")
        print("  Try running with --debug to watch the browser and spot any issues.")
        return pd.DataFrame()

    # ── Step 2: TN SOS enrichment ─────────────────────────────────────────────
    if not skip_sos:
        print("[2/2] Looking up ownership via TN Secretary of State...")
        clinics = enrich_with_sos(clinics)
        print(f"\n  Done.\n")
    else:
        print("[2/2] Skipping TN SOS step.\n")

    # ── Step 3: Export ────────────────────────────────────────────────────────
    df = pd.DataFrame(clinics)
    df = _reorder_columns(df)
    df.to_csv(OUTPUT_FILE, index=False)

    print(f"  Results saved to: {OUTPUT_FILE}")
    _print_summary(df)

    return df


if __name__ == "__main__":
    args = sys.argv[1:]
    run(
        skip_details="--fast" in args,
        skip_sos="--skip-sos" in args,
        debug="--debug" in args,
    )