from django.core.management.base import BaseCommand

from apps.subscriptions.services import expire_due_subscriptions


class Command(BaseCommand):
    help = "Mark subscriptions past their end date as expired"

    def handle(self, *args, **options):
        count = expire_due_subscriptions()
        self.stdout.write(f"Expired {count} subscription(s)")