"""The print worker: the process that actually takes jobs off the queue.

    python manage.py run_worker            # service: loop for ever
    python manage.py run_worker --drain    # print everything waiting, then exit
    python manage.py run_worker --once     # print at most one job, then exit

Nothing in the web request prints. A job sits in QUEUED until a worker claims it,
because printing can take a minute and a browser should never wait for that.
Run this in its own terminal (or as a service) and leave it running.
"""
import logging
import time

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.printing import services
from apps.printing.backends import get_backend
from apps.printing.models import PrintJob
from apps.printing.queue import get_queue

log = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Claim queued print jobs and print them"

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true",
                            help="Print one job, then exit")
        parser.add_argument("--drain", action="store_true",
                            help="Print everything waiting, then exit")
        parser.add_argument("--idle", type=float,
                            default=settings.WORKER_IDLE_SECONDS,
                            help="Seconds to sleep when the queue is empty")

    def handle(self, *args, **options):
        backend = get_backend()
        if not backend.available():
            self.stderr.write(self.style.ERROR(
                f"The {backend.name} backend is not available. Check "
                f"PRINT_BACKEND and the printer settings in .env."))
            return

        queue = get_queue()
        one_shot = options["once"] or options["drain"]
        if not one_shot:
            self.stdout.write(self.style.SUCCESS(
                f"Worker running. backend={backend.name} queue={queue.name} "
                f"depth={queue.depth()}  (Ctrl+C to stop)"))

        printed = 0
        failed = 0

        while True:
            job = services.process_next()

            if job is None:
                if one_shot:
                    self.stdout.write(self.style.SUCCESS(
                        f"Queue empty. Printed {printed}, failed {failed}."))
                    return
                time.sleep(options["idle"])
                continue

            if job.status == PrintJob.Status.PRINTED:
                printed += 1
                self.stdout.write(self.style.SUCCESS(
                    f"  {job.code}  printed  {job.page_count} pages  "
                    f"{job.cost_credits} credits  -> {job.output_file or job.spooler_name}"))
            else:
                failed += 1
                self.stdout.write(self.style.WARNING(
                    f"  {job.code}  {job.get_status_display().lower()}  "
                    f"{job.failure_reason}"))

            if options["once"]:
                return
