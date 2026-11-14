import secrets
from datetime import timedelta

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


def _nouvelle_reference():
    """GDA-20261114-7F3A9C : lisible au téléphone, unique en pratique."""
    return f"GDA-{timezone.now():%Y%m%d}-{secrets.token_hex(3).upper()}"


class CommandeCredits(models.Model):
    """Une recharge de crédits, de la sélection du montant jusqu'au reçu.

    Le paiement est simulé pendant la bêta, mais la commande suit le même
    cycle qu'un vrai paiement mobile : créée → en attente de confirmation
    (code envoyé) → payée, échouée, annulée ou expirée. Les crédits ne sont
    ajoutés qu'au passage à « payée », une seule fois (`transaction`).
    """

    class Statut(models.TextChoices):
        CREEE = "creee", "En attente du moyen de paiement"
        EN_ATTENTE = "en_attente", "En attente de confirmation"
        PAYEE = "payee", "Payée"
        ECHOUEE = "echouee", "Échouée"
        ANNULEE = "annulee", "Annulée"
        EXPIREE = "expiree", "Expirée"

    STATUTS_OUVERTS = (Statut.CREEE, Statut.EN_ATTENTE)

    reference = models.CharField(
        "référence", max_length=32, unique=True, default=_nouvelle_reference
    )
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="commandes_credits",
        verbose_name="utilisateur",
    )
    montant_fcfa = models.PositiveIntegerField("montant (FCFA)")
    credits = models.PositiveIntegerField("crédits")
    statut = models.CharField(
        "statut", max_length=12, choices=Statut.choices, default=Statut.CREEE
    )
    moyen_paiement = models.CharField("moyen de paiement", max_length=20, blank=True)
    # Jamais le numéro complet : « +223 •• •• 45 67 » ou « Visa •••• 4242 ».
    detail_moyen = models.CharField("détail du moyen", max_length=40, blank=True)
    code_confirmation = models.CharField("code de confirmation", max_length=6, blank=True)
    tentatives_code = models.PositiveSmallIntegerField("tentatives de code", default=0)
    motif_echec = models.CharField("motif d'échec", max_length=160, blank=True)
    date_creation = models.DateTimeField("créée le", default=timezone.now)
    date_paiement = models.DateTimeField("payée le", null=True, blank=True)
    transaction = models.OneToOneField(
        JournalCredits,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="commande",
        verbose_name="crédits ajoutés",
    )

    class Meta:
        verbose_name = "commande de crédits"
        verbose_name_plural = "commandes de crédits"
        ordering = ["-date_creation", "-pk"]

    def __str__(self):
        return f"{self.reference} — {self.montant_fcfa} FCFA ({self.get_statut_display()})"

    @property
    def date_expiration(self):
        from credits.config import DUREE_VALIDITE_COMMANDE_MINUTES

        return self.date_creation + timedelta(minutes=DUREE_VALIDITE_COMMANDE_MINUTES)

    @property
    def est_ouverte(self):
        return self.statut in self.STATUTS_OUVERTS

    @property
    def nom_moyen(self):
        from credits.config import MOYENS_PAIEMENT

        for moyen in MOYENS_PAIEMENT:
            if moyen["code"] == self.moyen_paiement:
                return moyen["nom"]
        return ""

    @property
    def famille_moyen(self):
        from credits.config import MOYENS_PAIEMENT

        for moyen in MOYENS_PAIEMENT:
            if moyen["code"] == self.moyen_paiement:
                return moyen["famille"]
        return ""
