from django import forms

from apps.accounts.models import User
from apps.core.forms import StyledFormMixin
from apps.subscriptions.models import Plan


class MemberForm(StyledFormMixin, forms.ModelForm):
    """Create or edit a member. Passwords are set by invitation, never here."""

    class Meta:
        model = User
        fields = ["student_no", "first_name", "last_name", "email", "phone", "role"]
        widgets = {
            "student_no": forms.TextInput(attrs={"placeholder": "202202881"}),
            "first_name": forms.TextInput(attrs={"placeholder": "Welile"}),
            "last_name": forms.TextInput(attrs={"placeholder": "Maphosa"}),
            "email": forms.EmailInput(attrs={"placeholder": "name@student.uneswa.ac.sz"}),
            "phone": forms.TextInput(attrs={"placeholder": "+26876123456"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["role"].help_text = (
            "Administrators can reach this dashboard; students cannot.")
        if self.instance.pk:
            self.fields["student_no"].disabled = True

    def clean_student_no(self):
        value = self.cleaned_data["student_no"].strip()
        existing = User.objects.filter(student_no__iexact=value)
        if self.instance.pk:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise forms.ValidationError("Another account already uses that number.")
        return value


class PlanForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Plan
        fields = ["name", "price_cents", "duration_days", "grant_credits", "is_active"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Semester membership"}),
            "price_cents": forms.NumberInput(attrs={"placeholder": "15000"}),
            "duration_days": forms.NumberInput(attrs={"placeholder": "120"}),
            "grant_credits": forms.NumberInput(attrs={"placeholder": "1000"}),
        }
        help_texts = {
            "price_cents": "In cents: E150.00 is 15000.",
            "grant_credits": "10 credits = E1.00 of mono printing. 1000 = E100.",
        }


class SubscribeForm(StyledFormMixin, forms.Form):
    plan = forms.ModelChoiceField(queryset=Plan.objects.filter(is_active=True),
                                  label="Plan", empty_label=None)