"""Formulaires des comptes : inscription et modification du profil."""

from django.contrib.auth.forms import UserCreationForm
from django.forms import ModelForm

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


class ProfilForm(ModelForm):
    """Cas d'utilisation « Modifier son profil »."""

    class Meta:
        model = Utilisateur
        fields = ("nom", "email")

    def __init__(self, *args, verrouille=False, **kwargs):
        super().__init__(*args, **kwargs)
        if verrouille:
            for champ in self.fields.values():
                champ.disabled = True
