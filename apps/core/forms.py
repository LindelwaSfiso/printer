"""Give every widget our CSS class so templates never write class= in Python."""
from django import forms


def style_form(form):
    for field in form.fields.values():
        widget = field.widget
        if isinstance(widget, forms.CheckboxInput):
            widget.attrs.setdefault("class", "checkbox")
        elif isinstance(widget, forms.ClearableFileInput):
            widget.attrs.setdefault("class", "file-input")
        elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
            widget.attrs.setdefault("class", "input select")
        elif isinstance(widget, forms.Textarea):
            widget.attrs.setdefault("class", "input textarea")
        else:
            widget.attrs.setdefault("class", "input")
    return form


class StyledFormMixin:
    """Apply the classes on construction, for both GET and bound forms."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_form(self)