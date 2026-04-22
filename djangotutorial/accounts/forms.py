import re

from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.db import transaction

from leaderboard.models import User as LeaderboardUser

from .models import Profile


def _input_attrs(placeholder="", autocomplete=""):
    return {
        "class": "field-input",
        "placeholder": placeholder,
        "autocomplete": autocomplete,
    }


def parse_phone_number(raw: str):
    """Parse a Czech phone number to the 9-digit integer form used by leaderboard.User.number."""
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("420") and len(digits) == 12:
        digits = digits[3:]
    if len(digits) == 9:
        try:
            return int(digits)
        except ValueError:
            return None
    return None


class PhoneOrUsernameLoginForm(forms.Form):
    identifier = forms.CharField(
        label="Telefon nebo přezdívka",
        widget=forms.TextInput(attrs=_input_attrs("Telefon nebo přezdívka", "username")),
    )
    password = forms.CharField(
        label="Heslo",
        widget=forms.PasswordInput(attrs=_input_attrs("Heslo", "current-password")),
    )

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user_cache = None
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        identifier = cleaned.get("identifier")
        password = cleaned.get("password")
        if not identifier or not password:
            return cleaned

        username = None
        phone = parse_phone_number(identifier)
        if phone is not None:
            try:
                lb_user = LeaderboardUser.objects.get(number=phone)
                profile = getattr(lb_user, "profile", None)
                if profile is not None:
                    username = profile.user.username
            except LeaderboardUser.DoesNotExist:
                pass

        if username is None:
            if User.objects.filter(username=identifier).exists():
                username = identifier

        if username is None:
            raise forms.ValidationError("Uživatel nenalezen.")

        user = authenticate(self.request, username=username, password=password)
        if user is None:
            raise forms.ValidationError("Nesprávné heslo.")
        if not user.is_active:
            raise forms.ValidationError("Účet je deaktivovaný.")

        self.user_cache = user
        return cleaned

    def get_user(self):
        return self.user_cache


class CustomUserCreationForm(UserCreationForm):
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
        fields = ("first_name", "email", "phone", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].label = "Heslo"
        self.fields["password1"].widget = forms.PasswordInput(
            attrs=_input_attrs("Heslo", "new-password")
        )
        self.fields["password2"].label = "Potvrzení hesla"
        self.fields["password2"].widget = forms.PasswordInput(
            attrs=_input_attrs("Heslo znovu", "new-password")
        )
        if "username" in self.fields:
            del self.fields["username"]

    def clean_phone(self):
        raw = self.cleaned_data["phone"]
        phone = parse_phone_number(raw)
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
            username=self.cleaned_data["email"],
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


class ProfileEditForm(forms.Form):
    photo = forms.ImageField(
        label="Profilová fotka",
        required=False,
        widget=forms.FileInput(attrs={"class": "field-input", "accept": "image/*"}),
    )
    instagram = forms.CharField(
        label="Instagram",
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs=_input_attrs("@tvoj_instagram", "url")),
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        if user:
            from leaderboard.models import ProfileQuestion
            for question in ProfileQuestion.objects.all():
                field_name = f"question_{question.id}"
                self.fields[field_name] = forms.CharField(
                    label=question.text,
                    required=False,
                    widget=forms.Textarea(attrs={
                        "class": "field-input",
                        "rows": "3",
                        "placeholder": "Tvá odpověď...",
                    }),
                )

    def save(self):
        if not self.user:
            return
        profile, _ = Profile.objects.get_or_create(user=self.user)
        if "photo" in self.cleaned_data and self.cleaned_data["photo"]:
            profile.photo = self.cleaned_data["photo"]
        profile.instagram = self.cleaned_data.get("instagram", "")
        profile.save()

        from leaderboard.models import ProfileQuestion, ProfileAnswer
        for question in ProfileQuestion.objects.all():
            field_name = f"question_{question.id}"
            answer_text = self.cleaned_data.get(field_name, "")
            ProfileAnswer.objects.update_or_create(
                auth_user=self.user,
                question=question,
                defaults={"answer": answer_text},
            )
