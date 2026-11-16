from django.core.management.base import BaseCommand

from apps.billing.services import expire_due_invoices


class Command(BaseCommand):
    help = "Close unpaid invoices past their expiry"

    def handle(self, *args, **options):
        count = expire_due_invoices()
        self.stdout.write(f"Expired {count} invoice(s)")