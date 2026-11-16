"""Job lifecycle: hold credits, queue, print, capture or refund.

Ordering rule, kept everywhere: lock the job, then the credit account.
"""
import logging

from django.db import transaction
from django.utils import timezone

from apps.credits import services as credits

from .backends import PrintError, get_backend
from .models import PrintJob, Tariff
from .pricing import quote
from .queue import get_queue

log = logging.getLogger(__name__)


def create_draft(*, member, uploaded, cleaned) -> PrintJob:
    """Persist the upload and its price, before any credits are reserved."""
    pages = cleaned["page_count"]
    tariff = Tariff.current()
    priced = quote(
        page_count=pages,
        copies=cleaned["copies"],
        colour=cleaned["colour_mode"] == PrintJob.Colour.COLOUR,
        duplex=cleaned["sides"] == PrintJob.Sides.DUPLEX,
        a3=cleaned["paper"] == PrintJob.Paper.A3,
        tariff=tariff,
    )
    return PrintJob.objects.create(
        member=member,
        document=uploaded,
        original_name=uploaded.name[:200],
        page_count=pages,
        colour_mode=cleaned["colour_mode"],
        sides=cleaned["sides"],
        paper=cleaned["paper"],
        copies=cleaned["copies"],
        cost_credits=priced.total_credits,
        tariff_snapshot=priced.as_snapshot(tariff),
    )


@transaction.atomic
def confirm_job(job: PrintJob) -> PrintJob:
    """Reserve the credits and put the job in the queue. Idempotent."""
    job = PrintJob.objects.select_for_update().get(pk=job.pk)
    if job.status != PrintJob.Status.DRAFT:
        return job

    account = credits.ensure_account(job.member)
    credits.place_hold(account_id=account.id, credits=job.cost_credits)

    job.hold_credits = job.cost_credits
    job.save(update_fields=["hold_credits", "updated_at"])
    get_queue().push(job)
    log.info("job %s queued: %s credits held", job.code, job.cost_credits)
    return job


@transaction.atomic
def capture_job(job: PrintJob, *, pages=None, submission=None, actor=None) -> PrintJob:
    """The print succeeded: turn the reservation into a real charge, once."""
    job = PrintJob.objects.select_for_update().get(pk=job.pk)
    if job.status == PrintJob.Status.PRINTED:
        return job

    account = credits.ensure_account(job.member)
    # Release first, then debit: post_entry refuses to leave the balance below
    # the amount still held.
    credits.release_hold(account_id=account.id, credits=job.hold_credits)
    credits.post_entry(
        account_id=account.id,
        delta_credits=-job.cost_credits,
        kind="CAPTURE",
        reference=f"job:{job.id}:capture",
        memo=f"Printed {job.original_name} ({job.code})",
        job=job,
        created_by=actor,
    )

    job.hold_credits = 0
    job.status = PrintJob.Status.PRINTED
    job.printed_at = timezone.now()
    job.printed_pages = pages if pages is not None else job.page_count * job.copies
    if submission is not None:
        job.output_file = submission.output_path or job.output_file
        job.spooler_name = submission.spooler_name or job.spooler_name
        job.spooler_job_id = submission.spooler_job_id
    if actor is not None:
        job.processed_by = actor
    job.save(update_fields=["hold_credits", "status", "printed_at", "printed_pages",
                            "output_file", "spooler_name", "spooler_job_id",
                            "processed_by", "updated_at"])
    log.info("job %s printed: %s credits captured", job.code, job.cost_credits)
    return job


@transaction.atomic
def fail_job(job: PrintJob, reason: str, *, actor=None,
             status: str = PrintJob.Status.FAILED) -> PrintJob:
    """Release the reservation and record why. Never charges the member."""
    job = PrintJob.objects.select_for_update().get(pk=job.pk)
    if job.status in (PrintJob.Status.PRINTED, PrintJob.Status.CANCELLED):
        return job

    if job.hold_credits:
        account = credits.ensure_account(job.member)
        credits.release_hold(account_id=account.id, credits=job.hold_credits)

    job.hold_credits = 0
    job.status = status
    job.failure_reason = (reason or "")[:500]
    job.failed_at = timezone.now()
    if actor is not None:
        job.processed_by = actor
    job.save(update_fields=["hold_credits", "status", "failure_reason", "failed_at",
                            "processed_by", "updated_at"])
    log.warning("job %s %s: %s", job.code, status, reason)
    return job


@transaction.atomic
def retry_job(job: PrintJob, *, actor=None) -> PrintJob:
    """Put a failed job back in the queue with a fresh reservation."""
    job = PrintJob.objects.select_for_update().get(pk=job.pk)
    if job.status not in (PrintJob.Status.FAILED, PrintJob.Status.EXPIRED):
        raise ValueError("Only a failed or expired job can be retried.")

    account = credits.ensure_account(job.member)
    credits.place_hold(account_id=account.id, credits=job.cost_credits)

    job.hold_credits = job.cost_credits
    job.failure_reason = ""
    job.attempts += 1
    if actor is not None:
        job.processed_by = actor
    job.save(update_fields=["hold_credits", "failure_reason", "attempts",
                            "processed_by", "updated_at"])
    get_queue().push(job)
    return job


@transaction.atomic
def cancel_job(job: PrintJob, *, actor=None) -> PrintJob:
    """Member (or staff) cancels before printing. The reservation is released."""
    job = PrintJob.objects.select_for_update().get(pk=job.pk)
    if job.status not in (PrintJob.Status.DRAFT,) + PrintJob.LIVE_STATUSES:
        raise ValueError("This job can no longer be cancelled.")

    if job.status == PrintJob.Status.DRAFT:
        job.delete()
        return job

    return fail_job(job, "Cancelled before printing", actor=actor,
                    status=PrintJob.Status.CANCELLED)


def process_next(*, actor=None) -> PrintJob | None:
    """Claim one job and print it. Used by the worker and by the desk button."""
    job = get_queue().pop()
    if job is None:
        return None

    backend = get_backend()
    try:
        submission = backend.submit(job, job.document.path)
    except PrintError as exc:
        return fail_job(job, str(exc), actor=actor)

    outcome = backend.wait(job, submission)
    if outcome.ok:
        return capture_job(job, pages=outcome.pages, submission=submission,
                           actor=actor)
    return fail_job(job, outcome.detail or "the printer did not confirm the job",
                    actor=actor)


def process_all(*, actor=None, limit: int = 25) -> list[PrintJob]:
    """Drain the queue, bounded so a web request cannot run for ever."""
    processed = []
    for _ in range(limit):
        job = process_next(actor=actor)
        if job is None:
            break
        processed.append(job)
    return processed
