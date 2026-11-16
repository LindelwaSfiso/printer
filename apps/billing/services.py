import logging

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.core.utils import normalize_txn_id
from apps.credits.models import CreditEntry
from apps.credits.services import ensure_account, post_entry

from .models import Invoice

log = logging.getLogger(__name__)


class InvoiceError(Exception):
    """Something the member or administrator needs to read and act on."""


@transaction.atomic
def create_invoice(*, member, amount_cents: int) -> Invoice:
    if not settings.TOPUP_MIN_CENTS <= amount_cents <= settings.TOPUP_MAX_CENTS:
        raise ValidationError(
            f"Top-ups must be between "
            f"E{settings.TOPUP_MIN_CENTS / 100:,.2f} and "
            f"E{settings.TOPUP_MAX_CENTS / 100:,.2f}.")
    rate = settings.CREDITS_PER_RAND
    return Invoice.objects.create(
        member=member,
        amount_cents=amount_cents,
        credits=amount_cents * rate // 100,
        rate_credits_per_rand=rate,
    )


@transaction.atomic
def submit_transaction_id(*, invoice: Invoice, txn_id: str, payer_phone: str,
                          proof=None) -> Invoice:
    invoice = Invoice.objects.select_for_update().get(pk=invoice.pk)
    if not invoice.can_submit:
        raise InvoiceError("This invoice is no longer open for submission.")

    clean = normalize_txn_id(txn_id)
    if len(clean) < 6:
        raise InvoiceError("Enter the full transaction ID from your payment SMS.")

    # Keep the audit trail of an earlier wrong attempt without holding the
    # uniqueness slot it occupies.
    if invoice.momo_txn_id and invoice.momo_txn_id != clean:
        invoice.superseded_txn_ids = list(invoice.superseded_txn_ids) + [
            invoice.momo_txn_id]
    invoice.momo_txn_id = clean

    invoice.payer_phone = payer_phone.strip()
    if proof:
        invoice.proof_file = proof
    invoice.status = Invoice.Status.AWAITING_APPROVAL
    invoice.submitted_at = timezone.now()
    invoice.attempts += 1
    invoice.rejection_reason = ""

    try:
        # A savepoint: if the unique index rejects the transaction ID, the outer
        # transaction stays usable and the caller gets a message it can show.
        with transaction.atomic():
            invoice.save()
    except IntegrityError:
        raise InvoiceError(
            "That transaction ID has already been used on another invoice. "
            "Check your SMS and try again, or speak to the treasurer.")
    log.info("invoice %s submitted for approval (txn %s)", invoice.reference, clean)
    return invoice


@transaction.atomic
def approve_invoice(*, invoice: Invoice, by) -> Invoice:
    invoice = Invoice.objects.select_for_update().get(pk=invoice.pk)
    if invoice.status == Invoice.Status.APPROVED:
        return invoice
    if invoice.status != Invoice.Status.AWAITING_APPROVAL:
        raise InvoiceError("Only an invoice awaiting approval can be approved.")
    if not invoice.momo_txn_id:
        raise InvoiceError("This invoice has no transaction ID.")

    account = ensure_account(invoice.member)
    post_entry(
        account_id=account.id,
        delta_credits=invoice.credits,
        kind=CreditEntry.Kind.TOPUP,
        reference=f"invoice:{invoice.id}:credit",
        memo=f"{invoice.reference} approved ({invoice.amount_rand})",
        invoice=invoice,
        created_by=by,
    )

    invoice.status = Invoice.Status.APPROVED
    invoice.decided_at = timezone.now()
    invoice.decided_by = by
    invoice.save(update_fields=["status", "decided_at", "decided_by", "updated_at"])
    log.info("invoice %s approved by %s", invoice.reference, by.student_no)
    return invoice


@transaction.atomic
def reject_invoice(*, invoice: Invoice, by, reason: str) -> Invoice:
    invoice = Invoice.objects.select_for_update().get(pk=invoice.pk)
    if invoice.status != Invoice.Status.AWAITING_APPROVAL:
        raise InvoiceError("Only an invoice awaiting approval can be rejected.")
    if not reason.strip():
        raise InvoiceError("Give a reason so the member knows what to fix.")

    invoice.status = Invoice.Status.REJECTED
    invoice.rejection_reason = reason.strip()[:200]
    invoice.decided_at = timezone.now()
    invoice.decided_by = by
    invoice.save(update_fields=["status", "rejection_reason", "decided_at",
                                "decided_by", "updated_at"])
    log.info("invoice %s rejected by %s: %s", invoice.reference, by.student_no, reason)
    return invoice


@transaction.atomic
def cancel_invoice(*, invoice: Invoice) -> Invoice:
    invoice = Invoice.objects.select_for_update().get(pk=invoice.pk)
    if invoice.status != Invoice.Status.AWAITING_PAYMENT:
        raise InvoiceError("Only an unpaid invoice can be cancelled.")
    invoice.status = Invoice.Status.CANCELLED
    invoice.save(update_fields=["status", "updated_at"])
    return invoice


def expire_due_invoices() -> int:
    return Invoice.objects.filter(
        status__in=[Invoice.Status.AWAITING_PAYMENT, Invoice.Status.AWAITING_APPROVAL],
        expires_at__lt=timezone.now(),
    ).update(status=Invoice.Status.EXPIRED, updated_at=timezone.now())