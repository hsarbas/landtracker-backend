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


def _make_summary_table(page_w: float, title_id: str | None, owner: str | None, tech_desc: str | None):
    margin = 28
    avail_w = page_w - (2 * margin)
    label_col_w = 120

    styles = getSampleStyleSheet()
    label_style = ParagraphStyle(
        "label",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=12,
    )
    value_style = ParagraphStyle(
        "value",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=13,
        wordWrap="CJK",
    )

    def _p(txt: str | None, style: ParagraphStyle) -> Paragraph:
        safe = escape(txt or "—").replace("\n", "<br/>")
        return Paragraph(safe, style)

    data = [
        [Paragraph("Title ID", label_style), _p(title_id, value_style)],
        [Paragraph("Owner", label_style), _p(owner, value_style)],
        [Paragraph("Technical Description", label_style), _p(tech_desc, value_style)],
    ]

    table = Table(
        data,
        colWidths=[label_col_w, avail_w - label_col_w],
        hAlign="LEFT",
    )
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#B0B0B0")),
        ("BACKGROUND", (0, 0), (0, -1), colors.lightblue),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))

    return table


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
    property_id: int | None = None,                   # <-- pass this to persist under a property
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    page_w, page_h = A4

    y = _draw_header(c, page_w, page_h)
    table = _make_summary_table(page_w, payload.title_id, payload.owner, payload.tech_desc)
    avail_w = page_w - (2 * 28)
    _, table_h = table.wrapOn(c, avail_w, 0)
    reserved_for_summary = 16 + table_h + 10 + 10

    c.setFont("Helvetica-Bold", 12)
    y -= 15

    if payload.snapshot:
        try:
            img_bytes = await _fetch_image_bytes(str(payload.snapshot))
            y = _draw_snapshot(c, page_w, y, img_bytes, reserve_below=reserved_for_summary)
        except Exception:
            c.setFont("Helvetica", 9)
            c.drawString(40, y, "Snapshot could not be embedded.")
            y -= 14

    y = _draw_summary_table(c, page_w, y, table)
    c.setFont("Helvetica", 8)
    c.drawRightString(page_w - 28, 18, "Page 1")
    c.showPage()
    c.save()

    buf.seek(0)
    pdf_bytes = buf.getvalue()

    saved_path = None
    if property_id is not None:
        # Optional: verify the property belongs to the current user
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

    # Stream back (and expose where it was saved if applicable)
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="LandTracker_Report.pdf"',
            "X-Report-Path": saved_path or "",
        },
    )
