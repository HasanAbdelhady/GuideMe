from django import forms
from django.contrib.auth.forms import PasswordChangeForm as DjangoPasswordChangeForm
from django.contrib.auth.forms import (
    UserChangeForm,
    UserCreationForm,
)
from .models import CustomUser


class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(
            attrs={
                "class": "w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-100"
            }
        ),
    )
    username = forms.CharField(
        widget=forms.TextInput(
            attrs={
                "class": "w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-100"
            }
        )
    )
    password1 = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "class": "w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-100"
            }
        )
    )
    password2 = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "class": "w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-100"
            }
        )
    )

    profile_image = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={"class": "hidden", "accept": "image/*"}),
    )

    learning_style_visual = forms.IntegerField(initial=0, required=False)
    learning_style_auditory = forms.IntegerField(initial=0, required=False)
    learning_style_kinesthetic = forms.IntegerField(initial=0, required=False)
    learning_style_reading = forms.IntegerField(initial=0, required=False)

    custom_interests = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "w-full p-2 border border-gray-300 rounded-lg",
                "placeholder": "Enter additional interests...",
            }
        ),
    )

    preferred_study_time = forms.ChoiceField(
        choices=CustomUser.STUDY_TIME_CHOICES,
        widget=forms.Select(
            attrs={"class": "w-full p-2 border border-gray-300 rounded-lg"}
        ),
    )
    quiz_preference = forms.ChoiceField(
        choices=CustomUser.QUIZ_PREFERENCE_CHOICES,
        widget=forms.Select(
            attrs={"class": "w-full p-2 border border-gray-300 rounded-lg"}
        ),
    )

    class Meta:  # type: ignore[override]
        model = CustomUser
        fields = (
            "username",
            "email",
            "profile_image",
            "learning_style_visual",
            "learning_style_auditory",
            "learning_style_kinesthetic",
            "learning_style_reading",
            "custom_interests",
            "preferred_study_time",
            "quiz_preference",
        )

    def clean(self):
        # Override clean to specifically remove interests from cleaned_data
        # This ensures that any 'interests' data in POST won't be validated against form fields
        cleaned_data = super().clean()
        if "interests" in self.data:
            # Don't validate 'interests' field - we'll handle it manually in the view
            pass
        return cleaned_data

    def clean_username(self):
        username = self.cleaned_data["username"]
        if CustomUser.objects.filter(username=username).exists():
            raise forms.ValidationError("This username is already taken.")
        return username


class CustomUserChangeForm(UserChangeForm):
    password = None  # Remove password field from the form

    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(
            attrs={
                "class": "w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-100"
            }
        ),
    )
    profile_image = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={"class": "hidden", "accept": "image/*"}),
    )

    learning_style_visual = forms.IntegerField(initial=0, required=False)
    learning_style_auditory = forms.IntegerField(initial=0, required=False)
    learning_style_kinesthetic = forms.IntegerField(initial=0, required=False)
    learning_style_reading = forms.IntegerField(initial=0, required=False)

    custom_interests = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "w-full p-2 border border-gray-300 rounded-lg",
                "placeholder": "Enter additional interests...",
            }
        ),
    )

    preferred_study_time = forms.ChoiceField(
        choices=CustomUser.STUDY_TIME_CHOICES,
        widget=forms.Select(
            attrs={"class": "w-full p-2 border border-gray-300 rounded-lg"}
        ),
    )
    quiz_preference = forms.ChoiceField(
        choices=CustomUser.QUIZ_PREFERENCE_CHOICES,
        widget=forms.Select(
            attrs={"class": "w-full p-2 border border-gray-300 rounded-lg"}
        ),
    )

    class Meta:  # type: ignore[override]
        model = CustomUser
        fields = (
            "email",
            "profile_image",
            "learning_style_visual",
            "learning_style_auditory",
            "learning_style_kinesthetic",
            "learning_style_reading",
            "interests",
            "custom_interests",
            "preferred_study_time",
            "quiz_preference",
        )


class PasswordChangeForm(DjangoPasswordChangeForm):
    old_password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "class": "w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-100"
            }
        )
    )
    new_password1 = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "class": "w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-100"
            }
        )
    )
    new_password2 = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "class": "w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-100"
            }
        )
    )
