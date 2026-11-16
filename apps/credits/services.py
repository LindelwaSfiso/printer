"""The only module allowed to change a credit balance.

Every other app imports from here. Each function is idempotent or atomic, and
each raise is a business rule that must not be bypassed.
"""
import logging

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import CreditAccount, CreditEntry

log = logging.getLogger(__name__)


class InsufficientCredits(Exception):
    """Not enough available credits for the requested operation."""


def ensure_account(user) -> CreditAccount:
    account, _ = CreditAccount.objects.get_or_create(member=user)
    return account


@transaction.atomic
def post_entry(*, account_id, delta_credits, kind, reference, memo="",
               job=None, invoice=None, subscription=None, created_by=None):
    """Move credits once. Re-running with the same reference is a no-op."""
    account = CreditAccount.objects.select_for_update().get(pk=account_id)

    existing = CreditEntry.objects.filter(reference=reference).first()
    if existing:
        return existing

    new_balance = account.balance_credits + delta_credits
    if new_balance < 0:
        raise InsufficientCredits("A balance cannot go below zero.")
    if new_balance < account.held_credits:
        raise InsufficientCredits("That would spend credits already reserved.")

    account.balance_credits = new_balance
    account.save(update_fields=["balance_credits", "updated_at"])

    entry = CreditEntry.objects.create(
        account=account, kind=kind, delta_credits=delta_credits,
        balance_after=new_balance, reference=reference, memo=memo,
        job=job, invoice=invoice, subscription=subscription,
        created_by=created_by,
    )
    log.info("credit %s %+d -> %d (%s)", kind, delta_credits, new_balance, reference)
    return entry


@transaction.atomic
def place_hold(*, account_id, credits):
    account = CreditAccount.objects.select_for_update().get(pk=account_id)
    if credits <= 0:
        raise ValidationError("A reservation must be positive.")
    if account.available_credits < credits:
        raise InsufficientCredits(
            f"This job needs {credits:,} credits but you have "
            f"{account.available_credits:,} available.")
    account.held_credits += credits
    account.save(update_fields=["held_credits", "updated_at"])
    return account


@transaction.atomic
def release_hold(*, account_id, credits):
    account = CreditAccount.objects.select_for_update().get(pk=account_id)
    account.held_credits = max(0, account.held_credits - credits)
    account.save(update_fields=["held_credits", "updated_at"])
    return account


def adjust(*, account_id, credits, memo, actor, reference=None):
    """Manual credit (cash at the desk, or a correction). Always attributed."""
    import uuid
    return post_entry(
        account_id=account_id, delta_credits=credits,
        kind=CreditEntry.Kind.ADJUSTMENT,
        reference=reference or f"manual:{uuid.uuid4().hex}",
        memo=memo[:200], created_by=actor,
    )