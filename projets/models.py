"""Les projets à auditer et les objectifs qu'on se fixe dessus.

Correspond aux classes Projet et ObjectifOptimisation du diagramme de classes.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone


class Projet(models.Model):
    """Classe Projet : un site web que l'utilisateur veut rendre plus sobre.

    Relations du diagramme :
      - Utilisateur 1 -- 0..* Projet
      - Projet 1 <>-- 0..* Analyse (composition, voir l'app analyses)
      - Projet 1 <>-- 0..* ObjectifOptimisation (composition, ci-dessous)
    """

    class Statut(models.TextChoices):
        ACTIF = "actif", "Actif"
        EN_PAUSE = "en_pause", "En pause"
        ARCHIVE = "archive", "Archivé"

    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="projets",
        verbose_name="propriétaire",
    )
    nom = models.CharField("nom du projet", max_length=150)
    description = models.TextField("description", blank=True)
    url = models.URLField("URL du site à analyser", max_length=500)
    date_creation = models.DateField("date de création", default=timezone.localdate)
    statut = models.CharField(
        "statut", max_length=10, choices=Statut.choices, default=Statut.ACTIF
    )

    class Meta:
        verbose_name = "projet"
        verbose_name_plural = "projets"
        ordering = ["-date_creation", "nom"]

    def __str__(self):
        return self.nom

    # --- opérations du diagramme ---

    def lancer_analyse(self, configuration=None, contexte=None):
        """lancerAnalyse(): Analyse — crée une nouvelle analyse en attente.

        On importe le modèle ici, et pas en haut du fichier, pour éviter que
        les deux apps s'importent mutuellement en boucle.
        """
        from analyses.models import Analyse

        return Analyse.creer_pour(self, configuration=configuration, contexte=contexte)

    def consulter_historique(self):
        """consulterHistorique(): List — toutes les analyses, de la plus récente."""
        return self.analyses.all()

    @property
    def derniere_analyse(self):
        """Raccourci pratique pour le tableau de bord."""
        return self.analyses.first()


class ObjectifOptimisation(models.Model):
    """Classe ObjectifOptimisation : une cible chiffrée sur un projet.

    Exemple : « poids de la page sous 500 Ko avant le 31/12 ».
    Relation du diagramme : Projet 1 <>-- 0..* ObjectifOptimisation.
    """

    class Statut(models.TextChoices):
        EN_COURS = "en_cours", "En cours"
        ATTEINT = "atteint", "Atteint"
        NON_ATTEINT = "non_atteint", "Non atteint"

    projet = models.ForeignKey(
        Projet,
        on_delete=models.CASCADE,
        related_name="objectifs",
        verbose_name="projet",
    )
    nom = models.CharField("intitulé de l'objectif", max_length=150)
    valeur_cible = models.FloatField("valeur à atteindre")
    unite = models.CharField("unité", max_length=20, default="Ko")
    date_limite = models.DateField("date limite", null=True, blank=True)
    statut = models.CharField(
        "statut", max_length=12, choices=Statut.choices, default=Statut.EN_COURS
    )

    class Meta:
        verbose_name = "objectif d'optimisation"
        verbose_name_plural = "objectifs d'optimisation"
        ordering = ["date_limite", "nom"]

    def __str__(self):
        return f"{self.nom} ({self.valeur_cible} {self.unite})"

    # --- opérations du diagramme ---

    def verifier_atteinte(self, valeur_mesuree):
        """verifierAtteinte(): boolean — la valeur mesurée respecte-t-elle la cible ?

        Un objectif de sobriété est toujours un plafond : on veut être en dessous.
        """
        return valeur_mesuree <= self.valeur_cible

    def mettre_a_jour_progression(self, valeur_mesuree):
        """mettreAJourProgression() : recalcule le statut après une analyse."""
        if self.verifier_atteinte(valeur_mesuree):
            self.statut = self.Statut.ATTEINT
        elif self.date_limite and self.date_limite < timezone.localdate():
            self.statut = self.Statut.NON_ATTEINT
        else:
            self.statut = self.Statut.EN_COURS
        self.save(update_fields=["statut"])
        return self.statut
