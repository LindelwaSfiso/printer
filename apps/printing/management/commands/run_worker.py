"""The print worker.

    python manage.py run_worker          # loop forever (the real deployment)
    python manage.py run_worker --once   # process at most one job

The web request never prints. This process claims from the queue, hands the job
to the backend, and records the outcome -- the same split you will use with a
real printer, so nothing changes when you switch PRINT_BACKEND.
"""
import logging
import time

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.printing import services
from apps.printing.backends import PrintError, get_backend
from apps.printing.queue import get_queue

log = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Claim queued print jobs and print them"

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true",
                            help="Process one job then exit")
        parser.add_argument("--idle", type=float,
                            default=settings.WORKER_IDLE_SECONDS,
                            help="Seconds to sleep when the queue is empty")

    def handle(self, *args, **options):
        backend = get_backend()
        if not backend.available():
            self.stderr.write(self.style.ERROR(
                f"The {backend.name} backend is not available. Check PRINT_BACKEND "
                f"and the printer settings in .env."))
            return

        queue = get_queue()
        self.stdout.write(self.style.SUCCESS(
            f"Worker ready. backend={backend.name} queue={queue.name} "
            f"depth={queue.depth()}"))

        while True:
            job = services.process_next()
            if job is None:
                if options["once"]:
                    self.stdout.write("Queue empty.")
                    return
                time.sleep(options["idle"])
                continue

            status = job.status
            style = self.style.SUCCESS if status == "PRINTED" else self.style.WARNING
            self.stdout.write(style(
                f"{job.code} -> {status}"
                + (f" ({job.failure_reason})" if job.failure_reason else "")))
            if options["once"]:
                return