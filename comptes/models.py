"""Les comptes : qui se connecte à Green Dev Africa, et ce qu'on lui notifie.

Correspond aux classes Utilisateur et Notification du diagramme de classes.
"""

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class Utilisateur(AbstractUser):
    """Classe Utilisateur du diagramme.

    On hérite de AbstractUser : Django fournit déjà l'e-mail, le mot de passe
    chiffré (attribut motDePasse du diagramme), la connexion et la déconnexion
    (seConnecter() / seDeconnecter()). On ajoute seulement ce que le diagramme
    demande en plus : le nom affiché et le rôle.
    """

    class Role(models.TextChoices):
        DEVELOPPEUR = "developpeur", "Développeur"
        ADMINISTRATEUR = "administrateur", "Administrateur"

    nom = models.CharField("nom complet", max_length=150)
    email = models.EmailField("adresse e-mail", unique=True)
    role = models.CharField(
        "rôle", max_length=20, choices=Role.choices, default=Role.DEVELOPPEUR
    )

    class Meta:
        verbose_name = "utilisateur"
        verbose_name_plural = "utilisateurs"
        ordering = ["nom"]

    def __str__(self):
        return self.nom or self.username

    # --- opérations du diagramme ---

    def est_administrateur(self):
        """Vrai si l'utilisateur peut régler les seuils des règles d'analyse."""
        return self.role == self.Role.ADMINISTRATEUR

    def modifier_profil(self, nom=None, email=None):
        """modifierProfil() : met à jour les informations du compte."""
        champs = []
        if nom is not None:
            self.nom = nom
            champs.append("nom")
        if email is not None:
            self.email = email
            champs.append("email")
        if champs:
            self.save(update_fields=champs)
        return self


class Notification(models.Model):
    """Classe Notification : un message envoyé à un utilisateur.

    Relation du diagramme : Utilisateur 1 -- 0..* Notification.
    """

    class Type(models.TextChoices):
        ANALYSE_TERMINEE = "analyse_terminee", "Analyse terminée"
        OBJECTIF_ATTEINT = "objectif_atteint", "Objectif atteint"
        PROBLEME_CRITIQUE = "probleme_critique", "Problème critique"
        INFORMATION = "information", "Information"

    utilisateur = models.ForeignKey(
        Utilisateur,
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name="utilisateur",
    )
    message = models.TextField("message")
    date_envoi = models.DateTimeField("date d'envoi", default=timezone.now)
    type = models.CharField(
        "type", max_length=20, choices=Type.choices, default=Type.INFORMATION
    )
    lu = models.BooleanField("lue", default=False)

    class Meta:
        verbose_name = "notification"
        verbose_name_plural = "notifications"
        ordering = ["-date_envoi"]

    def __str__(self):
        return f"{self.get_type_display()} — {self.utilisateur}"

    # --- opérations du diagramme ---

    @classmethod
    def envoyer(cls, utilisateur, message, type=Type.INFORMATION):
        """envoyer() : crée et enregistre la notification pour l'utilisateur."""
        return cls.objects.create(utilisateur=utilisateur, message=message, type=type)

    def marquer_comme_lue(self):
        """marquerCommeLue() : la cloche ne doit plus la compter."""
        if not self.lu:
            self.lu = True
            self.save(update_fields=["lu"])
        return self
