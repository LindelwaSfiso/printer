from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel


class Plan(TimeStampedModel):
    """A membership period that grants a fixed number of print credits."""

    name = models.CharField(max_length=60)
    price_cents = models.PositiveIntegerField(help_text="What the member pays, in cents")
    duration_days = models.PositiveSmallIntegerField(default=120)
    grant_credits = models.PositiveIntegerField(
        help_text="Fixed credits granted on activation (10 credits = E1.00)")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["price_cents"]

    def __str__(self):
        return f"{self.name} ({self.price_rand}, {self.grant_credits:,} credits)"

    @property
    def price_rand(self):
        from apps.core.utils import cents_to_rand
        return cents_to_rand(self.price_cents)

    @property
    def credit_value_rand(self):
        from apps.core.utils import credits_to_rand
        return credits_to_rand(self.grant_credits)


class Subscription(TimeStampedModel):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        EXPIRED = "EXPIRED", "Expired"
        CANCELLED = "CANCELLED", "Cancelled"

    member = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                               related_name="subscriptions")
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT)
    starts_on = models.DateField()
    ends_on = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices,
                              default=Status.ACTIVE)
    grants_credits = models.PositiveIntegerField(default=0)
    activated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                     on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["-starts_on"]

    def __str__(self):
        return f"{self.member.student_no} {self.plan.name} ({self.status})"

    @property
    def is_current(self):
        today = timezone.localdate()
        return (self.status == self.Status.ACTIVE
                and self.starts_on <= today <= self.ends_on)

    @property
    def days_left(self):
        return (self.ends_on - timezone.localdate()).days

    @classmethod
    def dates_for(cls, plan, starts_on=None):
        starts_on = starts_on or timezone.localdate()
        return starts_on, starts_on + timedelta(days=plan.duration_days - 1)