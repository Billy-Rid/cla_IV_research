# Setup & Usage Guide

## Prerequisites
- Python 3.10 or higher installed
- Terminal / VS Code integrated terminal

---

## One-Time Setup (run these once)

```bash
# 1. Navigate to the project folder
cd "c:/Users/willi/OneDrive/Desktop/Visual Studio Projects/cla_IV_research"

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Install the Chromium browser Playwright needs to scrape with
python -m playwright install chromium
```

---

## Running the Tool

```bash
# Full run (recommended) — scrapes Yelp + pulls TN SOS ownership data
python main.py

# Fast mode — skips per-clinic detail pages, quicker but less phone/website data
python main.py --fast

# Skip TN SOS step — useful if you just want the Yelp data first
python main.py --skip-sos

# Both flags combined
python main.py --fast --skip-sos
```

---

## Output

Results are saved to `data/nashville_iv_clinics.csv`

### Columns in the CSV

| Column | Description |
|---|---|
| name | Business name from Yelp |
| service_type | `In-Person` or `Mobile` |
| address_snippet | Neighborhood / address from Yelp |
| phone | Business phone |
| website | Business website |
| rating | Yelp star rating |
| review_count | Number of Yelp reviews |
| categories | Yelp categories |
| registered_name | Legal name in TN SOS registry |
| entity_type | LLC, Corporation, Sole Prop, etc. |
| sos_status | Active / Inactive / Not Found |
| sos_id | TN SOS filing number |
| date_formed | Date entity was registered in TN |
| registered_agent | Registered agent name |
| principal_office | Principal office address on file |
| owners_officers | Members / Officers / Organizers |

---

## How Long It Takes

| Mode | Approximate Time |
|---|---|
| Full run | 20–40 minutes (rate-limited to avoid blocks) |
| `--fast` | 8–15 minutes |
| `--skip-sos` | 5–10 minutes |
| `--fast --skip-sos` | 2–4 minutes |

---

## Notes

- Yelp and TN SOS are scraped with intentional delays to be respectful and avoid rate limits.
- If Yelp returns 0 results, try running again — occasional bot detection can block a session.
- Some clinics may show "Not Found in TN SOS" — they may operate under a DBA name (doing business as) that differs from their Yelp listing. You can manually search https://tnbear.tn.gov with alternate name variations.
- Mobile IV providers who operate as sole proprietors may not appear in the TN SOS registry at all if they haven't formed a formal entity.
