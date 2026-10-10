"""Formulaires des projets et des objectifs."""

from django import forms

from .models import ObjectifOptimisation, Projet


class ProjetForm(forms.ModelForm):
    """Cas d'utilisation « Créer un projet »."""

    class Meta:
        model = Projet
        fields = ("nom", "url", "description", "statut")
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "url": forms.URLInput(attrs={"placeholder": "https://monsite.ml"}),
        }
        help_texts = {"url": "L'adresse de la page qui sera analysée."}


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
                attrs={"placeholder": "Ramener la page d'accueil sous 500 Ko"}
            ),
        }
        help_texts = {
            "valeur_cible": "Un objectif de sobriété est un plafond : on veut passer en dessous."
        }
