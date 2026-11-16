"""Manager for the custom user model.

Django's stock `UserManager.create_superuser()` signature is
`create_superuser(username, email, password, **extra)`. Our login field is
`student_no`, so `manage.py createsuperuser` would call
`create_superuser(student_no=...)` and blow up with a missing `username`.

This manager keeps every behaviour of Django's (normalised email, password
hashing, `get_by_natural_key`, `with_perm`) and only changes which field is the
identity. `User.save()` still fills `username` from `student_no`, so the base
manager's assumptions elsewhere stay true.
"""
from django.contrib.auth.models import UserManager as DjangoUserManager


class UserManager(DjangoUserManager):
    """Users are keyed on the student number, not on a username."""

    def _create_user(self, student_no, email, password, **extra_fields):
        if not student_no:
            raise ValueError("A student number is required.")
        email = self.normalize_email(email)
        user = self.model(student_no=student_no.strip(), email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, student_no, email=None, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(student_no, email, password, **extra_fields)

    def create_superuser(self, student_no, email=None, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", "ADMIN")

        if extra_fields.get("is_staff") is not True:
            raise ValueError("A superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("A superuser must have is_superuser=True.")

        return self._create_user(student_no, email, password, **extra_fields)
