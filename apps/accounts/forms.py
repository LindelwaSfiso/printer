from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password

from apps.core.forms import StyledFormMixin

from .models import User


class LoginForm(StyledFormMixin, AuthenticationForm):
    """Student number + password."""

    username = forms.CharField(
        label="Student number",
        widget=forms.TextInput(attrs={
            "autocomplete": "username",
            "placeholder": "e.g. 202202881",
            "autofocus": True,
        }),
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={
            "autocomplete": "current-password",
            "placeholder": "Your password",
        }),
    )

    error_messages = {
        "invalid_login": "That student number and password do not match.",
        "inactive": "This account has been deactivated. Contact the society office.",
    }


class SetPasswordForm(StyledFormMixin, forms.Form):
    password1 = forms.CharField(
        label="New password", strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))
    password2 = forms.CharField(
        label="Confirm password", strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("password1"), cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "The two passwords do not match.")
        if p1 and self.user:
            try:
                validate_password(p1, self.user)
            except ValidationError as exc:
                self.add_error("password1", exc)
        return cleaned


class ProfileForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "phone"]


class MemberCreateForm(StyledFormMixin, forms.ModelForm):
    """Used from the admin area; no password field on purpose."""

    class Meta:
        model = User
        fields = ["student_no", "first_name", "last_name", "email", "phone", "role"]

    def clean_student_no(self):
        value = self.cleaned_data["student_no"].strip()
        if User.objects.filter(student_no__iexact=value).exists():
            raise ValidationError("An account with that student number already exists.")
        return value