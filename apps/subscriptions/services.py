import logging

from django.db import transaction
from django.utils import timezone

from apps.credits.services import ensure_account, post_entry

from .models import Subscription

log = logging.getLogger(__name__)


@transaction.atomic
def activate_subscription(subscription, *, actor=None):
    """Mark the subscription active and grant its credits exactly once.

    Idempotency lives in the ledger reference (`sub:<id>:allocation`), not in the
    status flag, so calling this twice -- or two admins clicking at once -- still
    produces one ALLOCATION entry.
    """
    subscription = Subscription.objects.select_for_update().get(pk=subscription.pk)

    subscription.status = Subscription.Status.ACTIVE
    subscription.grants_credits = subscription.plan.grant_credits
    subscription.activated_by = actor
    subscription.save(update_fields=["status", "grants_credits", "activated_by",
                                     "updated_at"])

    account = ensure_account(subscription.member)
    post_entry(
        account_id=account.id,
        delta_credits=subscription.grants_credits,
        kind="ALLOCATION",
        reference=f"sub:{subscription.id}:allocation",
        memo=f"{subscription.plan.name} - {subscription.grants_credits:,} credits",
        subscription=subscription,
        created_by=actor,
    )
    log.info("subscription %s active for %s", subscription.pk,
             subscription.member.student_no)
    return subscription


@transaction.atomic
def subscribe(*, member, plan, actor=None, starts_on=None):
    starts_on, ends_on = Subscription.dates_for(plan, starts_on)
    subscription = Subscription.objects.create(
        member=member, plan=plan, starts_on=starts_on, ends_on=ends_on,
        grants_credits=plan.grant_credits, status=Subscription.Status.ACTIVE,
        activated_by=actor,
    )
    return activate_subscription(subscription, actor=actor)


def expire_due_subscriptions():
    today = timezone.localdate()
    return Subscription.objects.filter(
        status=Subscription.Status.ACTIVE, ends_on__lt=today,
    ).update(status=Subscription.Status.EXPIRED)