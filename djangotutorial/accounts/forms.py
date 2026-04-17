from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        label="Uživatelské jméno",
        widget=forms.TextInput(attrs={
            "class": "field-input",
            "autofocus": True,
            "autocomplete": "username",
        }),
    )
    password = forms.CharField(
        label="Heslo",
        widget=forms.PasswordInput(attrs={
            "class": "field-input",
            "autocomplete": "current-password",
        }),
    )


class RegisterForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        label="E-mail",
        widget=forms.EmailInput(attrs={
            "class": "field-input",
            "autocomplete": "email",
        }),
    )

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Uživatelské jméno"
        self.fields["username"].widget.attrs.update({
            "class": "field-input",
            "autocomplete": "username",
        })
        self.fields["password1"].label = "Heslo"
        self.fields["password1"].widget.attrs.update({
            "class": "field-input",
            "autocomplete": "new-password",
        })
        self.fields["password2"].label = "Potvrzení hesla"
        self.fields["password2"].widget.attrs.update({
            "class": "field-input",
            "autocomplete": "new-password",
        })

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user
