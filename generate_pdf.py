"""
generate_pdf.py
---------------
Reads data/nashville_iv_clinics.csv and produces a formatted PDF report.

Each clinic is listed as:
    Company Name: Address/Office Location: Phone Number

Run from the cla_IV_research folder:
    python generate_pdf.py
"""

from pathlib import Path
import pandas as pd
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    HRFlowable,
    Table,
    TableStyle,
)

INPUT_CSV = Path("data/nashville_iv_clinics.csv")
OUTPUT_PDF = Path("data/nashville_iv_clinics.pdf")


def _clean(value) -> str:
    """Return a clean string, replacing missing/NaN with an empty string."""
    if pd.isna(value) or str(value).strip().lower() in ("nan", "none", ""):
        return ""
    return str(value).strip()


def _get_location(row: pd.Series) -> str:
    """
    Pick the best available location field.
    Mobile clinics use principal_office if address is missing.
    """
    address = _clean(row.get("address", ""))
    if address:
        return address

    # Fallback for mobile providers who don't have a fixed address
    principal = _clean(row.get("principal_office", ""))
    if principal:
        return principal

    address_snippet = _clean(row.get("address_snippet", ""))
    if address_snippet:
        return address_snippet

    return "Location not listed"


def _get_phone(row: pd.Series) -> str:
    phone = _clean(row.get("phone", ""))
    if phone:
        return phone
    return "Phone not listed"


def build_pdf(csv_path: Path = INPUT_CSV, pdf_path: Path = OUTPUT_PDF) -> Path:
    if not csv_path.exists():
        raise FileNotFoundError(
            f"CSV not found at {csv_path}.\n"
            "Run 'python main.py' first to generate the clinic data."
        )

    df = pd.read_csv(csv_path)

    if df.empty:
        raise ValueError("The CSV is empty — no clinics to report.")

    # Sort: In-Person first, then Mobile, then alphabetically within each group
    if "service_type" in df.columns:
        df["_sort_key"] = df["service_type"].apply(
            lambda x: 0 if str(x).strip() == "In-Person" else 1
        )
        df = df.sort_values(["_sort_key", "name"]).drop(columns=["_sort_key"])
    else:
        df = df.sort_values("name")

    # ── PDF Setup ─────────────────────────────────────────────────────────────
    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=LETTER,
        leftMargin=0.85 * inch,
        rightMargin=0.85 * inch,
        topMargin=1.0 * inch,
        bottomMargin=1.0 * inch,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "Title",
        parent=styles["Heading1"],
        fontSize=18,
        textColor=colors.HexColor("#1a1a2e"),
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "Subtitle",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.HexColor("#555555"),
        spaceAfter=16,
    )
    section_style = ParagraphStyle(
        "Section",
        parent=styles["Heading2"],
        fontSize=13,
        textColor=colors.HexColor("#16213e"),
        spaceBefore=14,
        spaceAfter=6,
    )
    clinic_name_style = ParagraphStyle(
        "ClinicName",
        parent=styles["Normal"],
        fontSize=11,
        textColor=colors.HexColor("#0f3460"),
        fontName="Helvetica-Bold",
        spaceBefore=8,
        spaceAfter=2,
    )
    detail_style = ParagraphStyle(
        "Detail",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.HexColor("#333333"),
        leading=15,
        leftIndent=12,
    )
    note_style = ParagraphStyle(
        "Note",
        parent=styles["Normal"],
        fontSize=8,
        textColor=colors.HexColor("#888888"),
        spaceAfter=2,
        leftIndent=12,
    )

    story = []

    # ── Header ────────────────────────────────────────────────────────────────
    story.append(Paragraph("Nashville IV Clinic Competitor Report", title_style))
    story.append(Paragraph(
        f"Total clinics: {len(df)}  |  "
        f"In-Person: {len(df[df.get('service_type', pd.Series()) == 'In-Person']) if 'service_type' in df.columns else 'N/A'}  |  "
        f"Mobile: {len(df[df.get('service_type', pd.Series()) == 'Mobile']) if 'service_type' in df.columns else 'N/A'}",
        subtitle_style,
    ))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#1a1a2e")))
    story.append(Spacer(1, 10))

    # ── Clinic Sections ───────────────────────────────────────────────────────
    current_section = None

    for _, row in df.iterrows():
        service_type = _clean(row.get("service_type", "In-Person")) or "In-Person"

        # Print section header when service type changes
        if service_type != current_section:
            current_section = service_type
            label = "In-Person Clinics" if service_type == "In-Person" else "Mobile IV Providers"
            story.append(Spacer(1, 6))
            story.append(Paragraph(label, section_style))
            story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#aaaaaa")))

        name = _clean(row.get("name", "")) or "Unknown Clinic"
        location = _get_location(row)
        phone = _get_phone(row)

        # Main formatted line: Company Name: Address: Phone
        story.append(Paragraph(name, clinic_name_style))
        story.append(Paragraph(
            f"{name}:  {location}:  {phone}",
            detail_style,
        ))

        # Optional enrichment lines (show if available)
        entity_type = _clean(row.get("entity_type", ""))
        owners = _clean(row.get("owners_officers", ""))
        rating = _clean(row.get("rating", ""))
        website = _clean(row.get("website", ""))

        notes = []
        if entity_type:
            notes.append(f"Entity: {entity_type}")
        if owners:
            notes.append(f"Owners/Officers: {owners}")
        if rating:
            notes.append(f"Google Rating: {rating} ★")
        if website:
            notes.append(f"Website: {website}")

        for note in notes:
            story.append(Paragraph(note, note_style))

        story.append(Spacer(1, 4))

    # ── Footer note ───────────────────────────────────────────────────────────
    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cccccc")))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "Data sourced from Google Maps and TN Secretary of State public registry. "
        "For ownership verification, cross-reference at tnbear.tn.gov.",
        ParagraphStyle("Footer", parent=styles["Normal"], fontSize=7, textColor=colors.HexColor("#aaaaaa")),
    ))

    doc.build(story)
    return pdf_path


if __name__ == "__main__":
    try:
        out = build_pdf()
        print(f"PDF saved to: {out}")
    except FileNotFoundError as e:
        print(f"Error: {e}")
    except ValueError as e:
        print(f"Error: {e}")