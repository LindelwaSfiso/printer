"""Create a usable starting point: a tariff, a plan, an admin and demo members.

    python manage.py seed_demo
    python manage.py seed_demo --reset

Safe to run twice: it skips anything that already exists.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.billing.services import create_invoice, submit_transaction_id
from apps.credits.services import ensure_account, post_entry
from apps.printing.models import Tariff
from apps.subscriptions.models import Plan
from apps.subscriptions.services import subscribe

User = get_user_model()


class Command(BaseCommand):
    help = "Seed a tariff, a plan, an administrator and demo members"

    def add_arguments(self, parser):
        parser.add_argument("--password", default="esprints123",
                            help="Password for the seeded accounts")
        parser.add_argument("--reset", action="store_true",
                            help="Delete seeded demo members first")

    @transaction.atomic
    def handle(self, *args, **options):
        password = options["password"]

        tariff = Tariff.current()
        tariff.mono_a4_credits = 10
        tariff.colour_a4_credits = 40
        tariff.a3_multiplier_percent = 200
        tariff.duplex_discount_percent = 10
        tariff.minimum_charge_credits = 10
        tariff.save()
        self.stdout.write(f"Tariff: mono {tariff.mono_a4_credits} / colour "
                          f"{tariff.colour_a4_credits} credits per A4 side")

        plan, _ = Plan.objects.get_or_create(
            name="Semester membership",
            defaults={"price_cents": 15000, "duration_days": 120,
                      "grant_credits": 1000, "is_active": True})
        self.stdout.write(f"Plan: {plan.name} ({plan.price_rand}, "
                          f"{plan.grant_credits:,} credits)")

        admin, created = User.objects.get_or_create(
            student_no="ADMIN001",
            defaults={"username": "ADMIN001", "first_name": "Society",
                      "last_name": "Treasurer", "email": "treasurer@esprints.local",
                      "phone": "+26876120000", "role": User.Role.ADMIN,
                      "is_staff": True, "is_superuser": True})
        admin.set_password(password)
        admin.is_staff = True
        admin.is_superuser = True
        admin.save()
        ensure_account(admin)
        self.stdout.write(("Created" if created else "Updated")
                          + f" administrator: ADMIN001 / {password}")

        if options["reset"]:
            User.objects.filter(student_no__in=["202202881", "202203442"]).delete()

        demo = [
            ("202202881", "Welile", "Maphosa", "+26876123456"),
            ("202203442", "Nokuthula", "Dlamini", "+26876234567"),
        ]
        for student_no, first, last, phone in demo:
            member, created = User.objects.get_or_create(
                student_no=student_no,
                defaults={"username": student_no, "first_name": first,
                          "last_name": last,
                          "email": f"{student_no}@student.uneswa.ac.sz",
                          "phone": phone, "role": User.Role.MEMBER,
                          "invitation_accepted_at": timezone.now()})
            if created:
                member.set_password(password)
                member.save()
                ensure_account(member)
            if not member.active_subscription:
                subscribe(member=member, plan=plan, actor=admin)
            self.stdout.write(("Created" if created else "Kept") + f" member {student_no}")

        # One invoice waiting for approval, so the dashboard has something real.
        member = User.objects.get(student_no="202202881")
        if not member.invoices.exists():
            invoice = create_invoice(member=member, amount_cents=2000)
            submit_transaction_id(
                invoice=invoice, txn_id="MP26071412345",
                payer_phone=member.phone)
            self.stdout.write(f"Demo invoice {invoice.reference} awaiting approval")

        # A little history so the chart is not flat.
        account = ensure_account(member)
        if not account.entries.filter(reference__startswith="demo:").exists():
            post_entry(account_id=account.id, delta_credits=300, kind="TOPUP",
                       reference="demo:topup",
                       memo="Demo top-up (seeded)", created_by=admin)
            self.stdout.write("Demo credit history added")

        self.stdout.write(self.style.SUCCESS(
            f"Done. Sign in as ADMIN001 / {password}, or as 202202881 / {password}."))