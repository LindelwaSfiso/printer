"""A cover sheet for every printed job, and the PDF the queue hands to a printer.

The ticket is page 1 of what gets printed but is never billed: the price was
fixed from the document's own page count before this runs.
"""
import logging
from io import BytesIO

from django.conf import settings
from pypdf import PdfReader, PdfWriter

log = logging.getLogger(__name__)


def _ticket_bytes(job) -> bytes | None:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas
    except ImportError:                      # reportlab is optional
        log.warning("reportlab is not installed; printing without a cover sheet")
        return None

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    pdf.setFillColorRGB(0.07, 0.07, 0.09)
    pdf.setFont("Helvetica-Bold", 20)
    pdf.drawString(20 * mm, height - 30 * mm, "ESprints")
    pdf.setFont("Helvetica", 11)
    pdf.drawString(20 * mm, height - 37 * mm, settings.SOCIETY_NAME)

    pdf.setFont("Helvetica-Bold", 15)
    pdf.drawString(20 * mm, height - 55 * mm, f"Job {job.code}")

    rows = [
        ("Student", f"{job.member.student_no}   {job.member.get_full_name()}"),
        ("Document", job.original_name[:52]),
        ("Colour", job.get_colour_mode_display()),
        ("Sides", job.get_sides_display()),
        ("Paper", job.paper),
        ("Copies", str(job.copies)),
        ("Pages per copy", str(job.page_count)),
        ("Sheets", str(job.sheets_estimate)),
        ("Credits charged", f"{job.cost_credits:,}"),
        ("Queued", job.created_at.strftime("%d %b %Y, %H:%M")),
    ]
    y = height - 70 * mm
    for label, value in rows:
        pdf.setFont("Helvetica", 10)
        pdf.setFillColorRGB(0.45, 0.45, 0.5)
        pdf.drawString(20 * mm, y, label.upper())
        pdf.setFont("Helvetica", 12)
        pdf.setFillColorRGB(0.07, 0.07, 0.09)
        pdf.drawString(55 * mm, y, value)
        y -= 9 * mm

    pdf.setFont("Helvetica-Oblique", 9)
    pdf.setFillColorRGB(0.45, 0.45, 0.5)
    pdf.drawString(20 * mm, 20 * mm,
                   "Cover sheet - not billed. Keep it with the printout.")
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def render_pdf(job, source_path: str, destination_path: str) -> bool:
    """Write `destination_path`: the cover sheet (if enabled) then the document.

    Returns True when a cover sheet was included.
    """
    ticket = _ticket_bytes(job) if settings.PRINT_TICKET else None
    writer = PdfWriter()
    included = False

    if ticket:
        for page in PdfReader(BytesIO(ticket)).pages:
            writer.add_page(page)
        included = True

    reader = PdfReader(source_path)
    if reader.is_encrypted:
        raise ValueError("The stored PDF is encrypted and cannot be printed.")
    for page in reader.pages:
        writer.add_page(page)

    with open(destination_path, "wb") as handle:
        writer.write(handle)
    return included