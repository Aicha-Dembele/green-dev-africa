"""Filtres de gabarit maison.

Un filtre sert à transformer une valeur dans une page HTML. Celui-ci traduit
le nom technique d'un indicateur en intitulé lisible :

    {{ indicateur.nom|libelle }}   →   « Poids total de la page »

Pour l'utiliser dans un gabarit, il faut d'abord écrire {% load greendev %}.
"""

from django import template

from analyses.indicateurs import libelle_de, unite_de

register = template.Library()


@register.filter
def libelle(code):
    """« poids_total » → « Poids total de la page »."""
    return libelle_de(code)


@register.filter
def unite(code):
    """« poids_total » → « Ko »."""
    return unite_de(code)


@register.filter
def widget_accessible(champ):
    """Relie un champ invalide à ses erreurs pour les technologies d'assistance."""
    if not champ.errors:
        return champ
    identifiant = champ.auto_id
    return champ.as_widget(
        attrs={
            "aria-describedby": f"{identifiant}_erreurs",
            "aria-invalid": "true",
        }
    )
