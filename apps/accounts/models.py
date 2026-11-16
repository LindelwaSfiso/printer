from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel

from .managers import UserManager


class User(AbstractUser, TimeStampedModel):
    """A society member or an administrator.

    Accounts are created by an administrator -- there is no public signup. The
    student number is the login name, and the password is set through an emailed
    invitation link rather than typed in by the admin.
    """

    class Role(models.TextChoices):
        MEMBER = "MEMBER", "Student"
        ADMIN = "ADMIN", "Administrator"

    student_no = models.CharField(max_length=20, unique=True)
    phone = models.CharField(max_length=16, blank=True,
                             help_text="Mobile number, e.g. +26876123456")
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.MEMBER)
    invited_at = models.DateTimeField(null=True, blank=True)
    invitation_accepted_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey("self", null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+")

    USERNAME_FIELD = "student_no"
    REQUIRED_FIELDS = ["email", "first_name", "last_name"]

    objects = UserManager()

    class Meta:
        ordering = ["student_no"]

    def save(self, *args, **kwargs):
        if not self.username:
            self.username = self.student_no
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student_no} - {self.get_full_name() or self.username}"

    @property
    def display_name(self):
        return self.get_full_name() or self.student_no

    @property
    def initials(self):
        parts = (self.get_full_name() or self.student_no).split()
        return "".join(p[0] for p in parts[:2]).upper()

    @property
    def is_member(self):
        return self.role == self.Role.MEMBER

    @property
    def active_subscription(self):
        today = timezone.localdate()
        return self.subscriptions.filter(
            status="ACTIVE", starts_on__lte=today, ends_on__gte=today,
        ).order_by("-ends_on").first()

    @property
    def can_print(self):
        return self.is_active and self.is_member and self.active_subscription is not None