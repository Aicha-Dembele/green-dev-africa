"""Formulaires du parcours d'achat de crédits (paiement simulé)."""

import re
from datetime import date

from django import forms

from credits import config


class MontantForm(forms.Form):
    """Étape 1 : un pack ou un montant libre."""

    montant = forms.IntegerField(
        label="Montant en FCFA",
        error_messages={
            "required": "Choisis un pack ou saisis un montant.",
            "invalid": "Saisis un montant entier en FCFA.",
        },
    )

    def clean_montant(self):
        montant = self.cleaned_data["montant"]
        try:
            config.credits_pour_montant(montant)
        except ValueError as erreur:
            raise forms.ValidationError(str(erreur))
        return montant


def _chiffres(valeur):
    return re.sub(r"\D", "", valeur or "")


def masquer_telephone(indicatif, numero):
    """« +223 •• •• 45 67 » : assez pour se reconnaître, pas pour réutiliser."""
    return f"{indicatif} •• •• {numero[-4:-2]} {numero[-2:]}"


class PaiementForm(forms.Form):
    """Étape 2 : moyen de paiement et coordonnées correspondantes.

    Mode test : aucune donnée n'est transmise à un opérateur. Pour la carte,
    seuls les numéros de test sont acceptés et seuls les 4 derniers chiffres
    sont conservés.
    """

    moyen = forms.ChoiceField(
        choices=[(m["code"], m["nom"]) for m in config.MOYENS_PAIEMENT],
        widget=forms.RadioSelect,
        error_messages={"required": "Choisis un moyen de paiement."},
    )
    indicatif = forms.ChoiceField(choices=config.INDICATIFS, required=False, initial="+223")
    telephone = forms.CharField(required=False, max_length=20)
    titulaire = forms.CharField(required=False, max_length=80)
    numero_carte = forms.CharField(required=False, max_length=23)
    expiration = forms.CharField(required=False, max_length=7)
    cvc = forms.CharField(required=False, max_length=4)

    def famille(self):
        code = self.cleaned_data.get("moyen")
        for moyen in config.MOYENS_PAIEMENT:
            if moyen["code"] == code:
                return moyen["famille"]
        return ""

    def clean(self):
        donnees = super().clean()
        if self.famille() == "mobile":
            self._verifier_mobile(donnees)
        elif self.famille() == "carte":
            self._verifier_carte(donnees)
        return donnees

    def _verifier_mobile(self, donnees):
        numero = _chiffres(donnees.get("telephone"))
        if not numero:
            self.add_error("telephone", "Saisis le numéro du compte mobile money.")
        elif not 8 <= len(numero) <= 10:
            self.add_error("telephone", "Le numéro doit compter entre 8 et 10 chiffres.")
        donnees["telephone"] = numero
        if not donnees.get("indicatif"):
            donnees["indicatif"] = "+223"

    def _verifier_carte(self, donnees):
        numero = _chiffres(donnees.get("numero_carte"))
        if not (donnees.get("titulaire") or "").strip():
            self.add_error("titulaire", "Saisis le nom inscrit sur la carte.")
        if not numero:
            self.add_error("numero_carte", "Saisis le numéro de la carte.")
        elif numero not in (config.CARTE_TEST_ACCEPTEE, config.CARTE_TEST_REFUSEE):
            self.add_error(
                "numero_carte",
                "Mode test : utilise la carte de test 4242 4242 4242 4242. "
                "Ne saisis jamais une vraie carte.",
            )
        donnees["numero_carte"] = numero

        expiration = (donnees.get("expiration") or "").replace(" ", "")
        correspondance = re.fullmatch(r"(\d{2})/(\d{2})", expiration)
        if not correspondance:
            self.add_error("expiration", "Format attendu : MM/AA.")
        else:
            mois, annee = int(correspondance[1]), 2000 + int(correspondance[2])
            aujourd_hui = date.today()
            if not 1 <= mois <= 12:
                self.add_error("expiration", "Le mois doit être entre 01 et 12.")
            elif (annee, mois) < (aujourd_hui.year, aujourd_hui.month):
                self.add_error("expiration", "Cette carte est expirée.")

        if not re.fullmatch(r"\d{3,4}", donnees.get("cvc") or ""):
            self.add_error("cvc", "3 chiffres au dos de la carte.")

    def detail_moyen(self):
        """Ce que la commande conserve du moyen de paiement (masqué)."""
        donnees = self.cleaned_data
        if self.famille() == "mobile":
            return masquer_telephone(donnees["indicatif"], donnees["telephone"])
        return f"Visa •••• {donnees['numero_carte'][-4:]}"

    def sera_refuse(self):
        """Les cas de test qui simulent un refus de l'opérateur ou de la banque."""
        donnees = self.cleaned_data
        if self.famille() == "mobile":
            if donnees["telephone"].endswith(config.SUFFIXE_TELEPHONE_REFUSE):
                return "Solde mobile money insuffisant pour ce montant."
        elif donnees["numero_carte"] == config.CARTE_TEST_REFUSEE:
            return "Paiement refusé par la banque émettrice de la carte."
        return ""


class CodeConfirmationForm(forms.Form):
    """Étape 3 : le code reçu par SMS (mobile money) ou 3-D Secure (carte)."""

    code = forms.CharField(
        min_length=6,
        max_length=6,
        error_messages={
            "required": "Saisis le code à 6 chiffres.",
            "min_length": "Le code compte 6 chiffres.",
            "max_length": "Le code compte 6 chiffres.",
        },
    )

    def clean_code(self):
        code = _chiffres(self.cleaned_data["code"])
        if len(code) != 6:
            raise forms.ValidationError("Le code compte 6 chiffres.")
        return code
