"""Print backends: the seam between the queue and an actual printer.

The contract is deliberately tiny:
    submit(job, document_path) -> Submission   (raise PrintError if rejected)
    wait(job, submission)      -> Outcome      (did it print, fail, or unknown)
    status()                   -> dict         (for the desk console)

`pdf` is the current backend: it renders the job -- cover sheet plus document --
into `private_media/printout/` instead of paper. Everything above it (pricing,
holds, capture, retries) behaves exactly as it will with a real printer, so
switching to `windows` or `cups` is a settings change, not a rewrite.
"""
import logging
import os
import shutil
import subprocess
from dataclasses import dataclass

from django.conf import settings

from .ticket import render_pdf

log = logging.getLogger(__name__)

PRINTOUT_DIR = settings.MEDIA_ROOT / "printout"
WORK_DIR = PRINTOUT_DIR / "_work"


class PrintError(Exception):
    """The backend could not even hand the job over."""


@dataclass
class Submission:
    ok: bool
    detail: str = ""
    output_path: str = ""          # relative to MEDIA_ROOT, when we produced a file
    spooler_name: str = ""
    spooler_job_id: int | None = None
    pages: int | None = None


@dataclass
class Outcome:
    ok: bool
    detail: str = ""
    pages: int | None = None


def _ensure_dirs():
    PRINTOUT_DIR.mkdir(parents=True, exist_ok=True)
    WORK_DIR.mkdir(parents=True, exist_ok=True)


class BaseBackend:
    name = "base"
    label = "Unknown"

    def available(self) -> bool:
        return True

    def submit(self, job, document_path: str) -> Submission:
        raise NotImplementedError

    def wait(self, job, submission: Submission) -> Outcome:
        return Outcome(ok=True, detail=submission.detail, pages=submission.pages)

    def status(self) -> dict:
        return {"ok": True, "name": self.label, "detail": "ready", "queued": 0}


class PdfBackend(BaseBackend):
    """Print to a PDF file. Proves the pipeline; needs no hardware."""

    name = "pdf"
    label = "PDF output"

    def submit(self, job, document_path: str) -> Submission:
        _ensure_dirs()
        destination = PRINTOUT_DIR / f"{job.code}.pdf"
        try:
            ticketed = render_pdf(job, document_path, str(destination))
        except Exception as exc:                      # corrupt/encrypted document
            raise PrintError(f"could not prepare the PDF: {exc}") from exc

        relative = str(destination.relative_to(settings.MEDIA_ROOT)).replace("\\", "/")
        pages = (job.page_count + (1 if ticketed else 0)) * job.copies
        log.info("rendered %s -> %s", job.code, relative)
        return Submission(
            ok=True,
            detail=f"Rendered to PDF{' with cover sheet' if ticketed else ''}",
            output_path=relative,
            spooler_name=self.label,
            pages=job.page_count * job.copies,
        )


class WindowsSpoolerBackend(BaseBackend):
    """Send the PDF to an installed Windows print queue with SumatraPDF."""

    name = "windows"
    label = "Windows print queue"

    EXIT_CODES = {
        0: "success",
        2: "the file could not be opened",
        3: "the document does not allow printing",
        4: "the printer does not exist (check PRINTER_NAME)",
        5: "the printer driver or device failed",
        6: "printing is blocked by policy",
    }

    def available(self) -> bool:
        return bool(settings.PRINTER_NAME) and os.path.exists(settings.SUMATRA_PATH)

    def print_settings(self, job) -> str:
        parts = [
            "duplexlong" if job.sides == "DUPLEX" else "simplex",
            "color" if job.colour_mode == "COLOUR" else "monochrome",
            f"paper={job.paper}",
            f"docname={job.code}",
            # A PDF can carry its own NumCopies/Duplex defaults; ignore them so the
            # member is billed for exactly what they chose.
            "ignore-pdf-print-settings",
        ]
        if job.copies > 1:
            parts.append(f"{job.copies}x")
        return ",".join(parts)

    def submit(self, job, document_path: str) -> Submission:
        if not self.available():
            raise PrintError("The Windows printer is not configured.")
        _ensure_dirs()
        work = WORK_DIR / f"{job.code}.pdf"
        render_pdf(job, document_path, str(work))

        command = [
            settings.SUMATRA_PATH,
            "-print-to", settings.PRINTER_NAME,
            "-print-settings", self.print_settings(job),
            "-silent",
            str(work),
        ]
        try:
            completed = subprocess.run(command, capture_output=True, text=True,
                                       timeout=settings.PRINT_TIMEOUT_SECONDS,
                                       shell=False)
        except subprocess.TimeoutExpired as exc:
            raise PrintError("the print command timed out") from exc
        finally:
            work.unlink(missing_ok=True)

        if completed.returncode != 0:
            raise PrintError(self.EXIT_CODES.get(
                completed.returncode, f"SumatraPDF exited {completed.returncode}"))
        return Submission(ok=True, detail="accepted by the print queue",
                          spooler_name=settings.PRINTER_NAME,
                          pages=job.page_count * job.copies)

    def status(self) -> dict:
        ready = self.available()
        return {"ok": ready, "name": settings.PRINTER_NAME or "not configured",
                "detail": "ready" if ready else "PRINTER_NAME or SumatraPDF missing",
                "queued": 0}


class CupsBackend(BaseBackend):
    """Linux / Raspberry Pi: hand the PDF to CUPS with `lp`."""

    name = "cups"
    label = "CUPS queue"

    def available(self) -> bool:
        return bool(settings.PRINTER_NAME) and shutil.which("lp") is not None

    def submit(self, job, document_path: str) -> Submission:
        if not self.available():
            raise PrintError("CUPS (`lp`) or PRINTER_NAME is not available.")
        _ensure_dirs()
        work = WORK_DIR / f"{job.code}.pdf"
        render_pdf(job, document_path, str(work))

        command = [
            "lp", "-d", settings.PRINTER_NAME, "-t", job.code,
            "-o", f"sides={'two-sided-long-edge' if job.sides == 'DUPLEX' else 'one-sided'}",
            "-o", f"print-color-mode={'color' if job.colour_mode == 'COLOUR' else 'monochrome'}",
            "-o", f"media={job.paper}",
            "-o", "job-sheets=none",
        ]
        if job.copies > 1:
            command += ["-n", str(job.copies)]
        command.append(str(work))
        try:
            completed = subprocess.run(command, capture_output=True, text=True,
                                       timeout=settings.PRINT_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired as exc:
            raise PrintError("`lp` timed out") from exc
        finally:
            work.unlink(missing_ok=True)

        if completed.returncode != 0:
            raise PrintError(completed.stderr.strip() or "`lp` failed")
        return Submission(ok=True, detail=completed.stdout.strip(),
                          spooler_name=settings.PRINTER_NAME,
                          pages=job.page_count * job.copies)


_BACKENDS = {
    "pdf": PdfBackend,
    "windows": WindowsSpoolerBackend,
    "cups": CupsBackend,
}


def get_backend() -> BaseBackend:
    key = (settings.PRINT_BACKEND or "pdf").lower()
    try:
        return _BACKENDS[key]()
    except KeyError:
        raise PrintError(f"Unknown PRINT_BACKEND {key!r} "
                         f"(expected one of {', '.join(_BACKENDS)})")
