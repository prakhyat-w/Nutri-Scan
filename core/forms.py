from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True, help_text="Required.")

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")


class MealUploadForm(forms.Form):
    photo = forms.ImageField(
        label="Meal photo",
        help_text="Upload a JPG or PNG photo of your meal.",
        widget=forms.ClearableFileInput(attrs={"accept": "image/*", "id": "meal-photo-input"}),
    )
    notes = forms.CharField(
        label="Notes (optional)",
        required=False,
        max_length=300,
        widget=forms.TextInput(attrs={"placeholder": "e.g. Lunch at home"}),
    )
