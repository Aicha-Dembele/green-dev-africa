from django.conf import settings
from django.db import models
from django.db.models import Q, Sum
from django.utils import timezone


class SoldeCredits(models.Model):
    utilisateur = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="solde_credits",
        verbose_name="utilisateur",
    )
    solde = models.IntegerField("solde", default=0)

    class Meta:
        verbose_name = "solde de crédits"
        verbose_name_plural = "soldes de crédits"

    def __str__(self):
        return f"{self.utilisateur} : {self.solde} crédits"

    def recalculer(self):
        total = JournalCredits.objects.filter(utilisateur=self.utilisateur).aggregate(
            total=Sum("montant")
        )["total"] or 0
        self.solde = int(total)
        self.save(update_fields=["solde"])
        return self.solde

    def verifier(self):
        total = JournalCredits.objects.filter(utilisateur=self.utilisateur).aggregate(
            total=Sum("montant")
        )["total"] or 0
        total = int(total)
        return self.solde == total, {"solde": self.solde, "journal": total}


class JournalCredits(models.Model):
    class Type(models.TextChoices):
        BIENVENUE = "bienvenue", "Crédits de bienvenue"
        ACHAT_MANUEL = "achat_manuel", "Achat manuel"
        DEBIT_ANALYSE = "debit_analyse", "Débit analyse"
        REMBOURSEMENT = "remboursement", "Remboursement"
        AJUSTEMENT_ADMIN = "ajustement_admin", "Ajustement admin"

    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="credits_journal",
        verbose_name="utilisateur",
    )
    montant = models.IntegerField("montant")
    type = models.CharField(
        "type",
        max_length=20,
        choices=Type.choices,
        default=Type.AJUSTEMENT_ADMIN,
    )
    analyse = models.ForeignKey(
        "analyses.Analyse",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transactions_credits",
        verbose_name="analyse liée",
    )
    date = models.DateTimeField("date", default=timezone.now)
    note = models.CharField("note", max_length=255, blank=True)

    class Meta:
        verbose_name = "transaction de crédits"
        verbose_name_plural = "transactions de crédits"
        constraints = [
            models.UniqueConstraint(
                fields=["utilisateur", "analyse", "type"],
                condition=Q(type="debit_analyse"),
                name="unique_debit_par_analyse",
            ),
            models.UniqueConstraint(
                fields=["utilisateur", "analyse", "type"],
                condition=Q(type="remboursement"),
                name="unique_remboursement_par_analyse",
            ),
        ]
        ordering = ["-date", "-pk"]

    def __str__(self):
        return f"{self.utilisateur} — {self.montant} ({self.type})"
