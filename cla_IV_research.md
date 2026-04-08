# Nashville IV Clinic Competitor Research Tool
**Project:** Competitive intelligence map for in-person IV therapy clinics in Nashville, TN

---

## Goal
Build a tool that:
1. Finds every in-person IV therapy clinic in Nashville
2. Maps them geographically
3. Captures business structure data for each competitor

---

## Data Points to Capture Per Clinic

### Identity
- Business name
- Address / neighborhood
- Phone number
- Website
- Google Maps rating + review count

### Business Structure
- Business entity type (LLC, Corp, Sole Prop — check TN SOS)
- Owner / operator name (if public)
- Year founded / opened
- Number of locations (single vs. chain)

### Service Offering
- IV drip menu (hydration, vitamin, NAD+, etc.)
- Pricing per drip / membership pricing
- Add-ons (IM shots, boosters)
- Mobile IV option (yes/no)
- Walk-in vs. appointment only

### Operations
- Hours of operation
- Staffing model (RN, NP, MD on-site?)
- Medical director listed?

### Marketing & Online Presence
- Instagram / TikTok / Facebook presence
- Active promotions or membership programs
- Reviews sentiment (Google, Yelp)

---

## Tool Plan (Phases)

### Phase 1 — Data Collection (MVP)
- Script that queries Google Places API for IV clinics in Nashville
- Exports results to a CSV/JSON with all available fields
- Manual enrichment layer for business structure fields

### Phase 2 — Map Visualization
- Plot clinics on an interactive map (Folium or Plotly)
- Color-code by rating, price tier, or service type
- Neighborhood clustering view

### Phase 3 — Business Structure Enrichment
- Pull TN Secretary of State business registry data
- Match clinic names to registered entities
- Flag active vs. inactive registrations

### Phase 4 — Dashboard (Optional)
- Simple web dashboard (Streamlit or Flask)
- Filter/sort by any field
- Exportable reports

---

## Tech Stack (Proposed)
- **Language:** Python
- **APIs:** Google Places API, optionally Yelp Fusion API
- **Mapping:** Folium (interactive HTML map)
- **Data:** pandas, CSV/JSON output
- **Dashboard:** Streamlit (Phase 4)

---

## Next Steps
- [ ] Confirm tech stack with user
- [ ] Set up Google Places API key
- [ ] Build Phase 1 data collection script
