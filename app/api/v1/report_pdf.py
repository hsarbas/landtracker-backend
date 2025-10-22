from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from urllib.parse import urlsplit
from sqlalchemy.orm import Session
import io, httpx, os
from datetime import datetime
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from xml.sax.saxutils import escape
from app.core.deps import get_current_user
from app.core.config import settings
from app.schemas.report_pdf import ReportData
from app.db.session import get_db
from app.models.property_report import PropertyReport
from app.models.property import Property  # to verify ownership

router = APIRouter(prefix="/api/v1/report_pdf", tags=["reports"], dependencies=[Depends(get_current_user)])

# ---------- logo config ----------
LOGO_MAX_H = 55  # points
LOGO_MAX_W = 72  # points (to prevent super-wide logos)
LOGO_PATH = settings.lt_logo_path
REPORTS_DIR = settings.reports_dir


def _ensure_dir(p: str) -> None:
    os.makedirs(p, exist_ok=True)


# ---------- helpers ----------
def _hr(c: canvas.Canvas, page_w: float, y: float, *, margin: int = 28,
        thickness: float = 1, color=colors.HexColor("#CFCFCF")) -> None:
    """Draw a horizontal rule across the content width at y."""
    c.saveState()
    c.setStrokeColor(color)
    c.setLineWidth(thickness)
    c.line(margin, y, page_w - margin, y)
    c.restoreState()


async def _fetch_image_bytes(url: str) -> bytes:
    sp = urlsplit(url)
    if sp.scheme != "https" or sp.netloc != "maps.googleapis.com" or not sp.path.startswith("/maps/api/staticmap"):
        raise HTTPException(status_code=400, detail="Invalid snapshot host")
    timeout = httpx.Timeout(15.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        r = await client.get(url)
    if r.status_code != 200 or not r.content:
        raise HTTPException(status_code=502, detail=f"Static Maps upstream error ({r.status_code})")
    return r.content


def _try_load_logo() -> ImageReader | None:
    try:
        if LOGO_PATH and os.path.exists(LOGO_PATH):
            return ImageReader(LOGO_PATH)
    except FileNotFoundError:
        pass
    return None


def _draw_header(c: canvas.Canvas, page_w: float, page_h: float) -> float:
    """
    Draw header with (optional) logo on the left and text on the right.
    Returns the y-position just below the header separator.
    """
    margin_left = 28
    # Header band height and vertical positioning
    band_top = page_h - 28
    band_bottom = page_h - 70
    band_h = band_top - band_bottom
    center_y = band_bottom + band_h / 2

    # Try load logo
    logo = _try_load_logo()
    text_x = margin_left  # will shift if logo exists

    if logo:
        iw, ih = logo.getSize()
        scale = min(LOGO_MAX_W / iw, LOGO_MAX_H / ih)
        w = max(1, iw * scale)
        h = max(1, ih * scale)
        x = margin_left
        y = center_y - (h / 2)
        c.drawImage(logo, x, y, width=w, height=h, preserveAspectRatio=True, mask='auto')
        text_x = x + w + 15  # gap to the right of the logo

    # Title and generated timestamp
    c.setFont("Helvetica-Bold", 16)
    # baseline ~ a bit above center
    title_y = center_y + 3
    c.drawString(text_x, title_y, "LAND TRACKER SUMMARY REPORT")

    c.setFont("Helvetica", 9)
    from datetime import datetime
    c.drawString(text_x, title_y - 15, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # separator under header
    sep_y = page_h - 90
    _hr(c, page_w, sep_y)
    return sep_y  # caller can base the next content from here


def _draw_snapshot(c: canvas.Canvas, page_w: float, y: float, img_bytes: bytes, reserve_below: float = 0) -> float:
    """
    Draw the snapshot image scaled to fit the available box.
    Returns the y just after the section (including its separator).
    """
    img = ImageReader(io.BytesIO(img_bytes))
    iw, ih = img.getSize()

    margin = 28
    left = margin
    right = page_w - margin
    max_w = right - left

    # available height from current y to bottom margin, keeping space below
    max_h = max(0, (y - margin) - reserve_below)

    if max_w > 0 and max_h > 0:
        scale = min(max_w / iw, max_h / ih)
        w = max(1, iw * scale)
        h = max(1, ih * scale)
        x = (page_w - w) / 2
        c.drawImage(img, x, y - h, width=w, height=h, preserveAspectRatio=True, mask='auto')
        y = y - h - 5  # gap after image

    # separator under snapshot section
    # _hr(c, page_w, y)
    return y - 10  # small gap after separator


def _make_summary_table(page_w: float, title_id: str | None, owner: str | None, boundaries: list[dict] | None):
    margin = 28
    avail_w = page_w - (2 * margin)

    styles = getSampleStyleSheet()
    label_style = ParagraphStyle("label", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=10)
    value_style = ParagraphStyle("value", parent=styles["Normal"], fontName="Helvetica", fontSize=10, leading=13)

    def _p(txt: str | None, style: ParagraphStyle) -> Paragraph:
        from xml.sax.saxutils import escape
        return Paragraph(escape(txt or "—"), style)

    # Header info
    summary_data = [
        [Paragraph("Title ID", label_style), _p(title_id, value_style)],
        [Paragraph("Owner", label_style), _p(owner, value_style)],
    ]

    # Boundaries section
    boundary_rows = [
        [Paragraph("<b>NS</b>", label_style),
         Paragraph("<b>Deg</b>", label_style),
         Paragraph("<b>Min</b>", label_style),
         Paragraph("<b>EW</b>", label_style),
         Paragraph("<b>Distance (m)</b>", label_style)]
    ]

    if boundaries:
        for b in boundaries:
            boundary_rows.append([
                _p(b.get("ns"), value_style),
                _p(str(b.get("deg")), value_style),
                _p(str(b.get("min")), value_style),
                _p(b.get("ew"), value_style),
                _p(f"{b.get('distance'):.2f}", value_style),
            ])
    else:
        boundary_rows.append(["—"] * 5)

    # Combine summary and boundary tables visually stacked
    summary_table = Table(summary_data, colWidths=[100, avail_w - 100], hAlign="LEFT")
    summary_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#B0B0B0")),
        ("BACKGROUND", (0, 0), (0, -1), colors.lightblue),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))

    boundaries_table = Table(boundary_rows, colWidths=[60, 60, 60, 60, avail_w - 240])
    boundaries_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#B0B0B0")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightblue),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ]))

    return summary_table, boundaries_table


def _draw_summary_table(c: canvas.Canvas, page_w: float, y: float, table: Table) -> float:
    """Draw heading, table, and a separator below the summary section. Return the y after the separator."""
    margin = 28
    left = margin
    avail_w = page_w - (2 * margin)

    # Heading
    c.setFont("Helvetica-Bold", 12)
    # c.drawString(left, y, "Summary")
    y -= 16

    # Table
    _, h = table.wrapOn(c, avail_w, y)
    table.drawOn(c, left, y - h)
    y = (y - h) - 10  # gap after table

    # separator under summary section
    # _hr(c, page_w, y)
    return y - 10  # small gap after separator


@router.post("", response_class=StreamingResponse, summary="Generate Land Tracker PDF (server-side)")
async def generate_report_pdf(
    payload: ReportData,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Builds a one-page PDF:
      - Header (logo + title + timestamp)
      - Optional snapshot (Google Static Maps)
      - Summary table (Title ID, Owner)
      - Boundaries table (NS, Deg, Min, EW, Distance)
    Saves a copy under REPORTS_DIR/<user.id>/... and records a PropertyReport row.
    Streams the PDF back to the client.
    """
    # ---- Build PDF in-memory ----
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    page_w, page_h = A4

    # Header
    y = _draw_header(c, page_w, page_h)

    # Tables (summary + boundaries)
    summary_table, boundaries_table = _make_summary_table(
        page_w,
        payload.title_number,
        payload.owner,
        [b.dict() if hasattr(b, "dict") else b for b in (payload.boundaries or [])],
    )

    # Compute reserved space below the snapshot so it doesn't overlap tables
    avail_w = page_w - (2 * 28)
    _, summary_h = summary_table.wrapOn(c, avail_w, 0)
    _, boundaries_h = boundaries_table.wrapOn(c, avail_w, 0)

    # Rough layout gaps/paddings (mirrors helpers)
    #  - 16 for summary heading spacing inside _draw_summary_table
    #  - +10 after summary table (inside _draw_summary_table)
    #  - +18 for "Boundaries" heading
    #  - +10 after boundaries table
    #  - +10 extra breathing room
    reserved_for_sections = 16 + summary_h + 10 + 18 + boundaries_h + 10 + 10

    # Optional snapshot (above tables)
    c.setFont("Helvetica-Bold", 12)
    y -= 15
    if payload.snapshot:
        try:
            img_bytes = await _fetch_image_bytes(str(payload.snapshot))
            y = _draw_snapshot(c, page_w, y, img_bytes, reserve_below=reserved_for_sections)
        except Exception:
            c.setFont("Helvetica", 9)
            c.drawString(40, y, "Snapshot could not be embedded.")
            y -= 14

    # Draw summary table (Title ID, Owner)
    y = _draw_summary_table(c, page_w, y, summary_table)

    # Draw "Boundaries" section
    margin_left = 28
    c.setFont("Helvetica-Bold", 12)
    c.drawString(margin_left, y, "Boundaries")
    y -= 18

    _, bh = boundaries_table.wrapOn(c, avail_w, y)
    boundaries_table.drawOn(c, margin_left, y - bh)
    y -= bh + 10

    # Footer (page number)
    c.setFont("Helvetica", 8)
    c.drawRightString(page_w - 28, 18, "Page 1")

    c.showPage()
    c.save()

    # ---- Persist & respond ----
    buf.seek(0)
    pdf_bytes = buf.getvalue()

    saved_path = None
    property_id = payload.property_id
    if property_id is not None:
        # Verify property ownership
        prop = db.get(Property, property_id)
        if not prop or prop.user_id != user.id:
            raise HTTPException(status_code=403, detail="Not your property")

        # Save to disk
        _ensure_dir(REPORTS_DIR)
        user_dir = os.path.join(REPORTS_DIR, str(user.id))
        _ensure_dir(user_dir)
        fname = f"LandTracker_Report_p{property_id}_{datetime.now().strftime('%Y%m%d-%H%M%S')}.pdf"
        saved_path = os.path.join(user_dir, fname)
        with open(saved_path, "wb") as f:
            f.write(pdf_bytes)

        # Record in DB
        db.add(PropertyReport(property_id=property_id, file_path=saved_path, report_type="pdf"))
        db.commit()

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'inline; filename="LandTracker_Report.pdf"',
            "X-Report-Path": saved_path or "",
        },
    )

