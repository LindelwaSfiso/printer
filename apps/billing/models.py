"""Top-ups by invoice.

There is no payment API. The member pays the society's mobile-money number from
their own phone, quotes the invoice reference, then records the transaction ID
here. An administrator checks it against the statement and approves it, which
posts the credits exactly once.

The controls that make this trustworthy:
  * `reference` is unique and the member is told to type it in the payment;
  * `momo_txn_id` is unique across every invoice, so one payment cannot be
    claimed twice or by two people;
  * approval is idempotent (ledger reference `invoice:<id>:credit`);
  * every decision records who made it.
"""
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel
from apps.core.utils import cents_to_rand


class Invoice(TimeStampedModel):
    class Status(models.TextChoices):
        AWAITING_PAYMENT = "AWAITING_PAYMENT", "Awaiting payment"
        AWAITING_APPROVAL = "AWAITING_APPROVAL", "Awaiting approval"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        CANCELLED = "CANCELLED", "Cancelled"
        EXPIRED = "EXPIRED", "Expired"

    OPEN_STATUSES = (Status.AWAITING_PAYMENT, Status.AWAITING_APPROVAL,
                     Status.REJECTED)

    reference = models.CharField(max_length=20, unique=True, blank=True)
    member = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                               related_name="invoices")
    amount_cents = models.PositiveIntegerField()
    credits = models.PositiveIntegerField()
    rate_credits_per_rand = models.PositiveSmallIntegerField(default=10)
    status = models.CharField(max_length=18, choices=Status.choices,
                              default=Status.AWAITING_PAYMENT)

    # How the member says they paid.
    momo_txn_id = models.CharField(max_length=40, null=True, blank=True, unique=True)
    superseded_txn_ids = models.JSONField(default=list, blank=True)
    payer_phone = models.CharField(max_length=16, blank=True)
    proof_file = models.FileField(upload_to="invoices/proofs/", null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)

    # How the administrator decided.
    decided_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+")
    rejection_reason = models.CharField(max_length=200, blank=True)

    attempts = models.PositiveSmallIntegerField(default=0)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "created_at"])]

    def __str__(self):
        return f"{self.reference} {self.member.student_no} ({self.status})"

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(
                hours=settings.INVOICE_TTL_HOURS)
        super().save(*args, **kwargs)
        if not self.reference and self.pk:
            reference = f"ESP-{timezone.localdate():%Y}-{self.pk:04d}"
            Invoice.objects.filter(pk=self.pk).update(reference=reference)
            self.reference = reference

    # -- display -----------------------------------------------------------
    @property
    def amount_rand(self):
        return cents_to_rand(self.amount_cents)

    @property
    def credits_rand(self):
        from apps.core.utils import credits_to_rand
        return credits_to_rand(self.credits)

    @property
    def is_open(self):
        return self.status in self.OPEN_STATUSES

    @property
    def can_submit(self):
        return self.status in (self.Status.AWAITING_PAYMENT, self.Status.REJECTED)

    @property
    def is_overdue(self):
        return bool(self.expires_at and self.expires_at < timezone.now()
                    and self.is_open)
