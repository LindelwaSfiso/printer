"""Ledger integrity check: sum(entries) must equal the cached balance."""
from django.core.management.base import BaseCommand
from django.db.models import Sum

from apps.credits.models import CreditAccount


class Command(BaseCommand):
    help = "Verify every credit account reconciles with its ledger"

    def handle(self, *args, **options):
        problems = 0
        for account in CreditAccount.objects.select_related("member").all():
            total = account.entries.aggregate(s=Sum("delta_credits"))["s"] or 0
            if total != account.balance_credits:
                problems += 1
                self.stderr.write(
                    f"MISMATCH {account.member.student_no}: "
                    f"balance={account.balance_credits} ledger={total}")
            if account.held_credits > account.balance_credits:
                problems += 1
                self.stderr.write(
                    f"OVER-RESERVED {account.member.student_no}: "
                    f"held={account.held_credits} balance={account.balance_credits}")
        self.stdout.write(self.style.SUCCESS(f"Checked; {problems} problem(s)"))
        if problems:
            raise SystemExit(1)