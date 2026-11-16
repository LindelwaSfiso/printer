"""The print queue.

Today the queue *is* the `PrintJob` table: a row in QUEUED is a job waiting, and
claiming it is a conditional UPDATE, so two workers can never take the same job.
That is enough for one department machine and it needs no extra service.

When you move to Redis/Celery (Linux testing, more than one desk), implement the
same three methods on a `RedisQueue` and point `PRINT_QUEUE` at it:

    push(job)  -> publish the job id
    pop()      -> claim an id atomically (BLPOP), return a PrintJob or None
    depth()    -> queue length

Nothing outside this module knows which one is in use.
"""
import logging

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import PrintJob

log = logging.getLogger(__name__)


class JobQueue:
    name = "base"

    def push(self, job: PrintJob) -> PrintJob:
        raise NotImplementedError

    def pop(self):
        raise NotImplementedError

    def depth(self) -> int:
        raise NotImplementedError


class DatabaseQueue(JobQueue):
    name = "database"

    def push(self, job: PrintJob) -> PrintJob:
        """Make the job the next thing the worker will pick up."""
        PrintJob.objects.filter(pk=job.pk).update(
            status=PrintJob.Status.QUEUED, queued_at=timezone.now())
        job.refresh_from_db(fields=["status", "queued_at"])
        return job

    def pop(self):
        """Claim the oldest queued job, or return None.

        The UPDATE ... WHERE status='QUEUED' is the lock: only the caller whose
        UPDATE reported one row actually owns the job.
        """
        while True:
            with transaction.atomic():
                job = (PrintJob.objects
                       .filter(status=PrintJob.Status.QUEUED)
                       .order_by("queued_at", "created_at")
                       .first())
                if job is None:
                    return None
                claimed = PrintJob.objects.filter(
                    pk=job.pk, status=PrintJob.Status.QUEUED,
                ).update(status=PrintJob.Status.PRINTING,
                         claimed_at=timezone.now(),
                         attempts=F("attempts") + 1)
                if claimed == 1:
                    job.refresh_from_db()
                    return job

    def depth(self) -> int:
        return PrintJob.objects.filter(status=PrintJob.Status.QUEUED).count()


def get_queue() -> JobQueue:
    key = (getattr(settings, "PRINT_QUEUE", "database") or "database").lower()
    if key == "database":
        return DatabaseQueue()
    raise NotImplementedError(
        f"PRINT_QUEUE={key!r} is not implemented yet. Add a RedisQueue in "
        f"apps/printing/queue.py implementing push/pop/depth.")
