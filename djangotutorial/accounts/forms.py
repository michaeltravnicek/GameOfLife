from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.db import transaction

from leaderboard.models import User as LeaderboardUser
from leaderboard.utils import parse_phone_number

from .models import Profile


def _input_attrs(placeholder="", autocomplete=""):
    return {
        "class": "field-input",
        "placeholder": placeholder,
        "autocomplete": autocomplete,
    }


class CustomUserCreationForm(UserCreationForm):
    """Registration form: email as username, phone links to a leaderboard user."""
    first_name = forms.CharField(
        label="Jméno",
        max_length=150,
        widget=forms.TextInput(attrs=_input_attrs("Jméno", "given-name")),
    )
    email = forms.EmailField(
        label="E-mail",
        widget=forms.EmailInput(attrs=_input_attrs("tvuj@email.cz", "email")),
    )
    phone = forms.CharField(
        label="Telefon",
        required=True,
        widget=forms.TextInput(attrs=_input_attrs("731 005 976", "tel")),
        help_text="Zadej 9-místné české číslo. Slouží k propojení s tvými body.",
    )

    class Meta:
        model = User
        fields = ("first_name", "username", "email", "phone", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Keep the default `username` field (with its validators) but present it
        # as the public "přezdívka". It becomes the account's username.
        self.fields["username"].label = "Přezdívka"
        self.fields["username"].help_text = "Tvé veřejné jméno na webu."
        self.fields["username"].widget = forms.TextInput(
            attrs=_input_attrs("prezdivka", "username")
        )
        self.fields["password1"].label = "Heslo"
        self.fields["password1"].widget = forms.PasswordInput(
            attrs=_input_attrs("Heslo", "new-password")
        )
        self.fields["password2"].label = "Potvrzení hesla"
        self.fields["password2"].widget = forms.PasswordInput(
            attrs=_input_attrs("Heslo znovu", "new-password")
        )

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("Tato přezdívka je už obsazená.")
        return username

    def clean_phone(self):
        phone = parse_phone_number(self.cleaned_data["phone"])
        if phone is None:
            raise forms.ValidationError("Zadej platné 9-místné české číslo.")
        return phone

    def clean_email(self):
        email = self.cleaned_data["email"]
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Účet s tímto e-mailem už existuje.")
        return email

    def clean(self):
        cleaned = super().clean()
        phone = cleaned.get("phone")
        if phone is not None:
            lb_user = LeaderboardUser.objects.filter(number=phone).first()
            if lb_user is not None and Profile.objects.filter(leaderboard_user=lb_user).exists():
                raise forms.ValidationError(
                    "Účet s tímto telefonem už existuje. Zkus se přihlásit."
                )
        return cleaned

    @transaction.atomic
    def save(self, commit=True):
        user = User.objects.create_user(
            username=self.cleaned_data["username"],
            email=self.cleaned_data["email"],
            password=self.cleaned_data["password1"],
            first_name=self.cleaned_data["first_name"],
        )
        phone = self.cleaned_data["phone"]
        lb_user = LeaderboardUser.objects.filter(number=phone).first()
        if lb_user is None:
            lb_user = LeaderboardUser.objects.create(
                number=phone,
                name=self.cleaned_data["first_name"],
            )
        Profile.objects.create(user=user, leaderboard_user=lb_user)
        return user
