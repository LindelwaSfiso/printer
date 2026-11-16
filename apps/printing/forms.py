from django import forms

from apps.core.forms import StyledFormMixin

from .models import PrintJob


class UploadJobForm(StyledFormMixin, forms.Form):
    document = forms.FileField(
        label="PDF document",
        help_text="PDF only - up to 20 MB and 200 pages.",
        widget=forms.ClearableFileInput(attrs={"accept": "application/pdf"}),
    )
    colour_mode = forms.ChoiceField(
        label="Colour", choices=PrintJob.Colour.choices, initial=PrintJob.Colour.MONO)
    sides = forms.ChoiceField(
        label="Sides", choices=PrintJob.Sides.choices, initial=PrintJob.Sides.SIMPLEX)
    paper = forms.ChoiceField(
        label="Paper size", choices=PrintJob.Paper.choices, initial=PrintJob.Paper.A4)
    copies = forms.IntegerField(
        label="Copies", min_value=1, max_value=20, initial=1,
        widget=forms.NumberInput(attrs={"min": 1, "max": 20}))