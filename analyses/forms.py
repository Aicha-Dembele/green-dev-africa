"""Formulaires des analyses.

Le formulaire de lancement est particulier : ses champs de mesure sont
**construits à partir des règles actives en base**. Ajoute une règle dans
l'administration, et le champ correspondant apparaît ici tout seul.
"""

from django import forms

from .indicateurs import libelle_de, unite_de
from .models import (
    Analyse,
    ConfigurationAnalyse,
    RegleAnalyse,
    UtilisateurContexte,
)

PREFIXE_MESURE = "mesure_"


class LancerAnalyseForm(forms.Form):
    """Cas d'utilisation « Lancer une analyse d'une URL ».

    Trois blocs : les réglages de l'audit (ConfigurationAnalyse), le contexte
    du visiteur simulé (UtilisateurContexte) et les mesures relevées.

    Les mesures sont **facultatives** : laissées vides, l'application va
    chercher le site elle-même (voir `analyses/collecteur.py`). On ne les
    remplit que pour forcer une valeur, ou pour rejouer un audit fait
    ailleurs.
    """

    # --- réglages de l'audit ---
    type_audit = forms.ChoiceField(
        label="Type d'audit",
        choices=ConfigurationAnalyse.TypeAudit.choices,
        initial=ConfigurationAnalyse.TypeAudit.PAGE_UNIQUE,
    )
    mode_analyse = forms.ChoiceField(
        label="Mode d'analyse",
        choices=ConfigurationAnalyse.Mode.choices,
        initial=ConfigurationAnalyse.Mode.RAPIDE,
    )
    inclure_medias = forms.BooleanField(
        label="Inclure les images et vidéos", initial=True, required=False
    )
    inclure_javascript = forms.BooleanField(
        label="Inclure le JavaScript", initial=True, required=False
    )

    # --- contexte du visiteur simulé ---
    type_appareil = forms.ChoiceField(
        label="Appareil du visiteur",
        choices=UtilisateurContexte.Appareil.choices,
        initial=UtilisateurContexte.Appareil.MOBILE_BAS,
    )
    qualite_connexion = forms.ChoiceField(
        label="Qualité de connexion",
        choices=UtilisateurContexte.Connexion.choices,
        initial=UtilisateurContexte.Connexion.G3,
    )
    forfait_data = forms.ChoiceField(
        label="Forfait data",
        choices=UtilisateurContexte.Forfait.choices,
        initial=UtilisateurContexte.Forfait.LIMITE,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Un champ de mesure par règle active, créé à la volée.
        self.regles = list(RegleAnalyse.objects.filter(active=True))
        for regle in self.regles:
            unite = unite_de(regle.code)
            if regle.est_regle_de_comptage():
                aide = "Toute occurrence compte comme un défaut."
            else:
                aide = f"Maximum conseillé : {regle.seuil:g} {unite}".strip()

            self.fields[PREFIXE_MESURE + regle.code] = forms.FloatField(
                label=f"{libelle_de(regle.code)} ({unite})" if unite else libelle_de(regle.code),
                help_text=aide,
                required=False,
                min_value=0,
            )

    def champs_mesures(self):
        """Les champs de mesure seuls, pour les afficher à part dans le gabarit."""
        for regle in self.regles:
            yield self[PREFIXE_MESURE + regle.code]

    def mesure_automatique(self):
        """Vrai si l'utilisateur n'a rien saisi : on ira mesurer le site."""
        return not self.mesures()

    # --- ce que la vue utilise ---

    def configuration(self):
        """Les réglages, prêts pour `Analyse.creer_pour()`."""
        return {
            "type_audit": self.cleaned_data["type_audit"],
            "mode_analyse": self.cleaned_data["mode_analyse"],
            "inclure_medias": self.cleaned_data["inclure_medias"],
            "inclure_javascript": self.cleaned_data["inclure_javascript"],
        }

    def contexte(self):
        return {
            "type_appareil": self.cleaned_data["type_appareil"],
            "qualite_connexion": self.cleaned_data["qualite_connexion"],
            "forfait_data": self.cleaned_data["forfait_data"],
        }

    def mesures(self):
        """Les mesures remplies, sous la forme attendue par `Indicateur`."""
        releves = []
        for regle in self.regles:
            valeur = self.cleaned_data.get(PREFIXE_MESURE + regle.code)
            if valeur is None:
                continue
            releves.append(
                {
                    "nom": regle.code,
                    "valeur": valeur,
                    "unite": unite_de(regle.code),
                    "categorie": regle.categorie,
                }
            )
        return releves


class ComparaisonForm(forms.Form):
    """Cas d'utilisation « Comparer deux analyses (avant / après) ».

    Les deux listes ne proposent que les analyses terminées **de ce projet** :
    on ne peut pas comparer avec l'analyse d'un autre utilisateur.
    """

    analyse_avant = forms.ModelChoiceField(label="Analyse de départ", queryset=None)
    analyse_apres = forms.ModelChoiceField(label="Analyse d'arrivée", queryset=None)

    def __init__(self, projet, *args, **kwargs):
        super().__init__(*args, **kwargs)
        terminees = projet.analyses.filter(statut=Analyse.Statut.TERMINEE)
        self.fields["analyse_avant"].queryset = terminees
        self.fields["analyse_apres"].queryset = terminees

    def clean(self):
        donnees = super().clean()
        avant, apres = donnees.get("analyse_avant"), donnees.get("analyse_apres")
        if avant and apres and avant == apres:
            raise forms.ValidationError(
                "Choisis deux analyses différentes : comparer une analyse avec "
                "elle-même ne dit rien."
            )
        return donnees


class RegleSeuilForm(forms.ModelForm):
    """Cas d'utilisation « Régler les seuils des règles d'analyse » (administrateur)."""

    class Meta:
        model = RegleAnalyse
        fields = ("seuil", "active")
