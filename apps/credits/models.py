from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class CreditAccount(TimeStampedModel):
    """One wallet per member. `balance_credits` is a cache; CreditEntry is truth."""

    member = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                  related_name="credit_account")
    balance_credits = models.PositiveIntegerField(default=0)
    held_credits = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.member.student_no}: {self.balance_credits} credits"

    @property
    def available_credits(self):
        return self.balance_credits - self.held_credits

    @property
    def available_rand(self):
        from apps.core.utils import credits_to_rand
        return credits_to_rand(self.available_credits)

    @property
    def balance_rand(self):
        from apps.core.utils import credits_to_rand
        return credits_to_rand(self.balance_credits)

    @property
    def held_rand(self):
        from apps.core.utils import credits_to_rand
        return credits_to_rand(self.held_credits)


class CreditEntry(TimeStampedModel):
    """Append-only ledger. The `reference` makes every movement idempotent."""

    class Kind(models.TextChoices):
        ALLOCATION = "ALLOCATION", "Subscription credits"
        TOPUP = "TOPUP", "Top-up (approved invoice)"
        CAPTURE = "CAPTURE", "Printing charge"
        REFUND = "REFUND", "Refund"
        ADJUSTMENT = "ADJUSTMENT", "Manual adjustment"
        REVERSAL = "REVERSAL", "Reversal"

    account = models.ForeignKey(CreditAccount, on_delete=models.CASCADE,
                                related_name="entries")
    kind = models.CharField(max_length=12, choices=Kind.choices)
    delta_credits = models.IntegerField(help_text="Signed: positive in, negative out")
    balance_after = models.PositiveIntegerField()
    reference = models.CharField(max_length=80, unique=True)
    memo = models.CharField(max_length=200, blank=True)
    job = models.ForeignKey("printing.PrintJob", null=True, blank=True,
                            on_delete=models.SET_NULL, related_name="ledger_rows")
    invoice = models.ForeignKey("billing.Invoice", null=True, blank=True,
                                on_delete=models.SET_NULL, related_name="ledger_rows")
    subscription = models.ForeignKey("subscriptions.Subscription", null=True,
                                     blank=True, on_delete=models.SET_NULL)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "credit entries"
        indexes = [models.Index(fields=["account", "created_at"])]

    def __str__(self):
        sign = "+" if self.delta_credits >= 0 else ""
        return f"{self.kind} {sign}{self.delta_credits} ({self.reference})"

    @property
    def amount_rand(self):
        from apps.core.utils import credits_to_rand
        return credits_to_rand(abs(self.delta_credits))

    @property
    def is_credit(self):
        return self.delta_credits >= 0