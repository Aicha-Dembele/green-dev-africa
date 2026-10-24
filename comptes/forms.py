"""Formulaires des comptes : inscription et modification du profil."""

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import Utilisateur


class InscriptionForm(UserCreationForm):
    """Cas d'utilisation « Créer un compte ».

    UserCreationForm fournit déjà les deux champs de mot de passe et leur
    vérification ; on ajoute simplement le nom et l'adresse e-mail.
    """

    class Meta:
        model = Utilisateur
        fields = ("username", "nom", "email")
        labels = {"username": "Identifiant de connexion"}
        widgets = {
            "username": forms.TextInput(attrs={"placeholder": "Ex. aicha-dembele"}),
            "nom": forms.TextInput(attrs={"placeholder": "Ex. Aïcha Dembélé"}),
            "email": forms.EmailInput(attrs={"placeholder": "Ex. aicha@exemple.com"}),
        }
        help_texts = {
            "username": "Sans espace ni accent. C'est ce que tu saisiras pour te connecter."
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Par défaut, Django affiche ici la liste complète des règles de mot
        # de passe, sous forme de pavé. Une phrase courte suffit : les règles
        # restantes sont vérifiées de toute façon à l'envoi du formulaire.
        self.fields["password1"].help_text = "Au moins 8 caractères."
        self.fields["password2"].help_text = "Recopie-le pour éviter une faute de frappe."
        self.fields["password1"].widget.attrs["placeholder"] = "8 caractères minimum"
        self.fields["password2"].widget.attrs["placeholder"] = "Répète ton mot de passe"


class ConnexionForm(AuthenticationForm):
    """Formulaire de connexion avec des exemples courts pour les champs."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs["placeholder"] = "Ton identifiant"
        self.fields["password"].widget.attrs["placeholder"] = "Ton mot de passe"
