from django import forms
from django.conf import settings
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone

from .models import Profile


def _input_attrs(placeholder="", autocomplete=""):
    return {
        "class": "field-input",
        "placeholder": placeholder,
        "autocomplete": autocomplete,
    }


class CustomUserCreationForm(UserCreationForm):
    """Registration form: name, username, e-mail, password. Nothing else."""
    first_name = forms.CharField(
        label="Jméno",
        max_length=150,
        widget=forms.TextInput(attrs=_input_attrs("Jméno", "given-name")),
    )
    email = forms.EmailField(
        label="E-mail",
        widget=forms.EmailInput(attrs=_input_attrs("tvuj@email.cz", "email")),
    )
    # No phone field, and no phone anywhere else either — the number was dropped
    # from LeaderboardUser in migration 0026. It used to be the exact key that
    # matched an account to its player row, which meant collecting a number from
    # everyone for no other purpose. The e-mail is that key now: it creates the
    # account's own player, and adopts an archive player carrying the same
    # address. Anything less exact than that is an admin merge
    # (accounts.matching + leaderboard.merging).

    # Enforced here, not only in React: a client-side checkbox is a UX nicety,
    # but the record of consent has to be trustworthy, and anything posting
    # straight to the API would otherwise create an account with no consent at
    # all. `required=True` on a BooleanField rejects both a missing and a false
    # value.
    gdpr_consent = forms.BooleanField(
        label="Souhlas se zpracováním osobních údajů",
        required=True,
        error_messages={
            "required": "Bez souhlasu se zpracováním osobních údajů tě bohužel "
                        "nemůžeme zaregistrovat.",
        },
    )

    class Meta:
        model = User
        fields = ("first_name", "username", "email", "password1", "password2")

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
        # No '@': a handle doubles as a login identifier, and login matches a
        # username before an e-mail — so "victim@example.com" as a handle would
        # shadow that victim's e-mail login. Keep handles e-mail-free.
        if "@" in username:
            raise forms.ValidationError("Přezdívka nesmí obsahovat znak @.")
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("Tato přezdívka je už obsazená.")
        return username

    def clean_email(self):
        email = self.cleaned_data["email"]
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Účet s tímto e-mailem už existuje.")
        return email

    @transaction.atomic
    def save(self, commit=True):
        user = User.objects.create_user(
            username=self.cleaned_data["username"],
            email=self.cleaned_data["email"],
            password=self.cleaned_data["password1"],
            first_name=self.cleaned_data["first_name"],
        )
        Profile.objects.create(
            user=user,
            # Recorded from the server clock, not from anything the client sent
            # — a consent timestamp the user could choose is worthless as proof.
            gdpr_consent_at=timezone.now(),
            gdpr_consent_version=settings.PRIVACY_POLICY_VERSION,
        )
        # Every account is a player from the start: check-in refuses an account
        # with no leaderboard row, so postponing this would silently cost the
        # newcomer the points from their first event. Adopts an archive player
        # when the e-mail matches one — see ensure_leaderboard_user.
        from .services import ensure_leaderboard_user
        ensure_leaderboard_user(user)
        return user
