"""Formulaires des projets et des objectifs."""

import ipaddress
from urllib.parse import urlparse

from django import forms

from .models import ObjectifOptimisation, Projet


class ProjetForm(forms.ModelForm):
    """Cas d'utilisation « Créer un projet »."""

    class Meta:
        model = Projet
        fields = ("nom", "url", "description")
        widgets = {
            "nom": forms.TextInput(
                attrs={"placeholder": "Ex. Site vitrine de mon association"}
            ),
            "description": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Ex. Site de présentation et d'inscription de l'association.",
                }
            ),
            "url": forms.URLInput(attrs={"placeholder": "https://monsite.ml"}),
        }
        help_texts = {"url": "L'adresse de la page qui sera analysée."}

    def clean_url(self):
        url = self.cleaned_data["url"]
        decoupe = urlparse(url)
        if decoupe.scheme.lower() not in {"http", "https"}:
            raise forms.ValidationError("Utilise une adresse commençant par http:// ou https://.")
        hote = decoupe.hostname or ""
        try:
            ipaddress.ip_address(hote)
        except ValueError:
            pass
        else:
            raise forms.ValidationError(
                "Saisis le nom de domaine public du site, pas une adresse IP."
            )
        hote = hote.rstrip(".").lower()
        if hote == "localhost" or hote.endswith((".localhost", ".local", ".internal")):
            raise forms.ValidationError(
                "Cette adresse locale ou interne ne peut pas être ajoutée."
            )
        return url


class ObjectifForm(forms.ModelForm):
    """Cas d'utilisation « Se fixer un objectif d'optimisation »."""

    class Meta:
        model = ObjectifOptimisation
        fields = ("nom", "valeur_cible", "unite", "date_limite")
        widgets = {
            # type="date" fait apparaître le calendrier du navigateur,
            # sans une ligne de JavaScript.
            "date_limite": forms.DateInput(attrs={"type": "date"}),
            "nom": forms.TextInput(
                attrs={"placeholder": "Ex. Garder la page d'accueil sous 500 Ko"}
            ),
            "valeur_cible": forms.NumberInput(attrs={"placeholder": "Ex. 500"}),
            "unite": forms.TextInput(attrs={"placeholder": "Ex. Ko"}),
        }
        help_texts = {
            "valeur_cible": (
                "Un objectif de sobriété est un plafond : on veut passer en dessous."
            ),
            "date_limite": "Facultatif : laisse vide si tu n'as pas encore fixé de date.",
        }
