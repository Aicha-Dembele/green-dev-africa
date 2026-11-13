"""Formulaires des comptes : inscription, connexion et mot de passe oublié."""

from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordResetForm,
    SetPasswordForm,
    UserCreationForm,
)

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
        self.fields["password1"].help_text = "Au moins 12 caractères."
        self.fields["password2"].help_text = "Recopie-le pour éviter une faute de frappe."
        self.fields["password1"].widget.attrs["placeholder"] = "12 caractères minimum"
        self.fields["password2"].widget.attrs["placeholder"] = "Répète ton mot de passe"


class ConnexionForm(AuthenticationForm):
    """Formulaire de connexion avec des exemples courts pour les champs."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs["placeholder"] = "Ton identifiant"
        self.fields["password"].widget.attrs["placeholder"] = "Ton mot de passe"


class MotDePasseOublieForm(PasswordResetForm):
    """Étape 1 du « Mot de passe oublié » : la personne tape son adresse e-mail.

    Django fait déjà le plus important, on ne le refait pas :
    - il cherche le compte ACTIF qui porte cette adresse, majuscules ou non ;
    - il envoie le lien à l'adresse ENREGISTRÉE sur le compte, jamais ailleurs ;
    - si aucun compte n'a cette adresse, il n'envoie rien et ne le dit pas.
      Sinon, n'importe qui pourrait tester quelles adresses ont un compte.
    On change seulement l'intitulé et l'exemple affichés.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        champ = self.fields["email"]
        champ.label = "Adresse e-mail de ton compte"
        champ.widget.attrs.update({"placeholder": "Ex. aicha@exemple.com", "autofocus": True})


class NouveauMotDePasseForm(SetPasswordForm):
    """Étape 3 : la personne a cliqué sur le lien et choisit son nouveau mot de passe.

    Les règles sont les mêmes qu'à l'inscription (12 caractères, pas
    seulement des chiffres) ; on remplace juste le pavé d'aide de Django
    par les mêmes phrases courtes.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["new_password1"].help_text = "Au moins 12 caractères."
        self.fields["new_password2"].help_text = "Recopie-le pour éviter une faute de frappe."
        self.fields["new_password1"].widget.attrs.update(
            {"placeholder": "12 caractères minimum", "autofocus": True}
        )
        self.fields["new_password2"].widget.attrs["placeholder"] = "Répète ton mot de passe"
