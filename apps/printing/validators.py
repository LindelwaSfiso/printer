"""Reject anything that is not a printable, unencrypted PDF we can count."""
from django.core.exceptions import ValidationError
from pypdf import PdfReader

MAX_BYTES = 20 * 1024 * 1024
MAX_PAGES = 200


def inspect_pdf(upload) -> int:
    """Validate the upload and return its page count.

    Page count comes from the file itself, never from the browser, because it is
    what the member is charged for.
    """
    if upload.size > MAX_BYTES:
        raise ValidationError("That file is larger than 20 MB.")

    head = upload.read(5)
    upload.seek(0)
    if head != b"%PDF-":
        raise ValidationError(
            "Please upload a PDF. In Word or Google Docs, use File > "
            "Download/Save as PDF first.")

    try:
        reader = PdfReader(upload)
        if reader.is_encrypted:
            raise ValidationError("Password-protected PDFs cannot be printed.")
        pages = len(reader.pages)
    except ValidationError:
        raise
    except Exception:
        raise ValidationError("This PDF could not be read. Try exporting it again.")
    finally:
        upload.seek(0)

    if pages == 0:
        raise ValidationError("This PDF has no pages.")
    if pages > MAX_PAGES:
        raise ValidationError(f"The limit is {MAX_PAGES} pages per job.")
    return pages