import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel
from apps.core.utils import credits_to_rand


class Tariff(TimeStampedModel):
    """What one printed side costs, in credits.

    Rates are whole credits and the duplex discount is applied to the rate (not
    to the total) so every figure stays an integer. 10 credits = E1.00.
    """

    mono_a4_credits = models.PositiveIntegerField(default=10, help_text="Per A4 side")
    colour_a4_credits = models.PositiveIntegerField(default=40, help_text="Per A4 side")
    a3_multiplier_percent = models.PositiveSmallIntegerField(default=200)
    duplex_discount_percent = models.PositiveSmallIntegerField(default=10)
    minimum_charge_credits = models.PositiveIntegerField(default=10)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "tariff"

    def __str__(self):
        return (f"Mono {self.mono_a4_credits} / colour {self.colour_a4_credits} "
                f"credits per A4 side")

    @classmethod
    def current(cls):
        tariff = cls.objects.filter(is_active=True).order_by("-created_at").first()
        return tariff or cls.objects.create()


def job_upload_to(instance, filename):
    return f"jobs/{instance.member_id}/{uuid.uuid4().hex}.pdf"


class PrintJob(TimeStampedModel):
    """A submitted document and everything that happened to it."""

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Not confirmed"
        QUEUED = "QUEUED", "In the queue"
        PRINTING = "PRINTING", "Printing"
        PRINTED = "PRINTED", "Printed"
        FAILED = "FAILED", "Failed"
        CANCELLED = "CANCELLED", "Cancelled"
        EXPIRED = "EXPIRED", "Expired"

    class Colour(models.TextChoices):
        MONO = "MONO", "Black & white"
        COLOUR = "COLOUR", "Colour"

    class Sides(models.TextChoices):
        SIMPLEX = "SIMPLEX", "Single-sided"
        DUPLEX = "DUPLEX", "Double-sided"

    class Paper(models.TextChoices):
        A4 = "A4", "A4"
        A3 = "A3", "A3"

    # Statuses that still own a credit reservation.
    LIVE_STATUSES = (Status.QUEUED, Status.PRINTING)
    OPEN_STATUSES = (Status.DRAFT, Status.QUEUED, Status.PRINTING)

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    code = models.CharField(max_length=12, unique=True, null=True, blank=True)
    member = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                               related_name="jobs")
    document = models.FileField(upload_to=job_upload_to)
    original_name = models.CharField(max_length=200)
    page_count = models.PositiveIntegerField()
    colour_mode = models.CharField(max_length=6, choices=Colour.choices,
                                   default=Colour.MONO)
    sides = models.CharField(max_length=7, choices=Sides.choices,
                             default=Sides.SIMPLEX)
    paper = models.CharField(max_length=2, choices=Paper.choices, default=Paper.A4)
    copies = models.PositiveSmallIntegerField(default=1)

    cost_credits = models.PositiveIntegerField(default=0)
    tariff_snapshot = models.JSONField(default=dict, blank=True)
    hold_credits = models.PositiveIntegerField(default=0)

    status = models.CharField(max_length=10, choices=Status.choices,
                              default=Status.DRAFT)

    # What the print backend produced / where it sent it.
    output_file = models.CharField(max_length=300, blank=True)
    spooler_name = models.CharField(max_length=120, blank=True)
    spooler_job_id = models.IntegerField(null=True, blank=True)

    attempts = models.PositiveSmallIntegerField(default=0)
    queued_at = models.DateTimeField(null=True, blank=True)
    claimed_at = models.DateTimeField(null=True, blank=True)
    printed_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    printed_pages = models.PositiveIntegerField(null=True, blank=True)
    failure_reason = models.TextField(blank=True)
    processed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                     on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "created_at"])]

    def __str__(self):
        return f"{self.code or 'draft'} - {self.original_name} ({self.status})"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.code and self.pk:
            code = f"ESP-{self.pk:05d}"
            PrintJob.objects.filter(pk=self.pk).update(code=code)
            self.code = code

    # -- display helpers ---------------------------------------------------
    @property
    def cost_rand(self):
        return credits_to_rand(self.cost_credits)

    @property
    def sides_count(self):
        return self.page_count * self.copies

    @property
    def sheets_estimate(self):
        sides = self.sides_count
        return (sides + 1) // 2 if self.sides == self.Sides.DUPLEX else sides

    @property
    def is_live(self):
        return self.status in self.LIVE_STATUSES

    @property
    def summary(self):
        return (f"{self.get_colour_mode_display()}, {self.get_sides_display()}, "
                f"{self.paper}, {self.copies} x")

    def queue_position(self):
        """1-based position among queued jobs, or None if not queued."""
        if self.status != self.Status.QUEUED or not self.queued_at:
            return None
        return PrintJob.objects.filter(
            status=self.Status.QUEUED, queued_at__lt=self.queued_at).count() + 1
