from django import forms
from django.contrib.auth import get_user_model
User = get_user_model()
class ComposeForm(forms.Form):
    to = forms.ModelChoiceField(queryset=User.objects.exclude(username__iexact='hr_admin'), label="To")
    subject = forms.CharField(max_length=200, required=True, label="Subject")
    body = forms.CharField(widget=forms.Textarea, required=True, label="Message")