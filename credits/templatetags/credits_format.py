"""Mise en forme des montants : « 2 500 FCFA » avec des espaces insécables."""

from django import template

register = template.Library()

ESPACE_FINE = " "
ESPACE_INSECABLE = " "


@register.filter
def milliers(valeur):
    try:
        return f"{int(valeur):,}".replace(",", ESPACE_FINE)
    except (TypeError, ValueError):
        return valeur


@register.filter
def fcfa(valeur):
    nombre = milliers(valeur)
    if nombre is valeur:  # pas un nombre : rendu tel quel
        return valeur
    return f"{nombre}{ESPACE_INSECABLE}FCFA"
