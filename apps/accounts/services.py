"""Account creation and the emailed invitation.

The flow is: an administrator creates the account with an unusable password,
the member receives a link, sets a password, and is signed in. No password ever
travels by email.
"""
import logging

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from apps.credits.services import ensure_account

from .models import User

log = logging.getLogger(__name__)


def invite_url(user) -> str:
    """Absolute URL the member clicks to choose a password."""
    path = reverse("accounts:accept_invite", kwargs={
        "uidb64": urlsafe_base64_encode(force_bytes(user.pk)),
        "token": default_token_generator.make_token(user),
    })
    return f"{settings.SITE_URL}{path}"


def send_invite(user, *, request=None) -> str:
    """Email the invitation and return the URL (handy while running on console)."""
    url = invite_url(user)
    user.invited_at = timezone.now()
    user.save(update_fields=["invited_at", "updated_at"])

    body = (
        f"Hello {user.get_full_name() or user.student_no},\n\n"
        f"An account has been created for you on {settings.SOCIETY_NAME} "
        f"E-Printing (ESprints).\n\n"
        f"Student number: {user.student_no}\n\n"
        f"Choose your password here (the link expires in 3 days):\n{url}\n\n"
        f"If you were not expecting this, ignore this message and tell the "
        f"society office.\n\n"
        f"-- {settings.SOCIETY_NAME}"
    )
    send_mail(
        subject=f"Set up your ESprints account",
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email] if user.email else [],
        fail_silently=False,
    )
    log.info("invitation sent to %s (%s)", user.student_no, user.email or "no email")
    return url


def create_account(*, actor, student_no, first_name, last_name, email, phone,
                   role=User.Role.MEMBER, password=None):
    """Create a member (or administrator). Invitation is sent by the caller."""
    user = User(
        student_no=student_no.strip(),
        username=student_no.strip(),
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        email=email.strip(),
        phone=phone.strip(),
        role=role,
        is_staff=(role == User.Role.ADMIN),
        created_by=actor,
    )
    if password:
        user.set_password(password)
    else:
        user.set_unusable_password()
    user.save()
    ensure_account(user)
    return user


def accept_invite(user, password):
    user.set_password(password)
    user.invitation_accepted_at = timezone.now()
    user.save(update_fields=["password", "invitation_accepted_at", "updated_at"])
    return user