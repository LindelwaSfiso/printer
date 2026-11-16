"""Release reservations on jobs nobody collected."""
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.printing import services
from apps.printing.models import PrintJob


class Command(BaseCommand):
    help = "Release holds on jobs that sat in the queue too long"

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(hours=settings.JOB_EXPIRY_HOURS)
        stale = PrintJob.objects.filter(
            status__in=[PrintJob.Status.QUEUED, PrintJob.Status.PRINTING],
            created_at__lt=cutoff)
        count = 0
        for job in stale:
            services.fail_job(job, "Expired before printing",
                              status=PrintJob.Status.EXPIRED)
            count += 1
        self.stdout.write(f"Expired {count} job(s)")