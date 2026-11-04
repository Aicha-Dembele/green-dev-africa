from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.utils import timezone

from analyses.models import Analyse, ConfigurationAnalyse
from credits.config import (
    COUT_PAGE_HORS_QUOTA,
    COUT_SITE_COMPLET_APPROFONDI,
    COUT_SITE_COMPLET_RAPIDE,
    CREDITS_BIENVENUE,
    MODE_ANALYSE_APPROFONDI,
    MODE_ANALYSE_RAPIDE,
    QUOTA_GRATUIT_MENSUEL,
    TYPE_AUDIT_PAGE_UNIQUE,
    TYPE_AUDIT_SITE_COMPLET,
)
from credits.models import JournalCredits, SoldeCredits


def _normaliser_configuration(configuration):
    if isinstance(configuration, dict):
        return configuration
    if configuration is None:
        return {"type_audit": TYPE_AUDIT_PAGE_UNIQUE, "mode_analyse": MODE_ANALYSE_RAPIDE}
    return {
        "type_audit": getattr(configuration, "type_audit", TYPE_AUDIT_PAGE_UNIQUE),
        "mode_analyse": getattr(configuration, "mode_analyse", MODE_ANALYSE_RAPIDE),
    }


def compter_analyses_gratuites_du_mois(utilisateur, annee=None, mois=None):
    if utilisateur is None:
        return 0

    maintenant = timezone.now()
    annee = annee or maintenant.year
    mois = mois or maintenant.month

    return (
        Analyse.objects.filter(
            projet__utilisateur=utilisateur,
            date_analyse__year=annee,
            date_analyse__month=mois,
            statut=Analyse.Statut.TERMINEE,
        )
        .filter(configurations__type_audit=ConfigurationAnalyse.TypeAudit.PAGE_UNIQUE)
        .distinct()
        .count()
    )


def calculer_cout(configuration, utilisateur=None):
    conf = _normaliser_configuration(configuration)
    type_audit = conf.get("type_audit")
    mode_analyse = conf.get("mode_analyse")

    if type_audit in (TYPE_AUDIT_PAGE_UNIQUE, ConfigurationAnalyse.TypeAudit.PAGE_UNIQUE):
        quota_restant = QUOTA_GRATUIT_MENSUEL - compter_analyses_gratuites_du_mois(utilisateur)
        return 0 if quota_restant > 0 else COUT_PAGE_HORS_QUOTA

    if type_audit in (TYPE_AUDIT_SITE_COMPLET, ConfigurationAnalyse.TypeAudit.SITE_COMPLET):
        if str(mode_analyse) == MODE_ANALYSE_APPROFONDI:
            return COUT_SITE_COMPLET_APPROFONDI
        return COUT_SITE_COMPLET_RAPIDE

    return 0


def assurer_solde_utilisateur(utilisateur):
    solde, _ = SoldeCredits.objects.get_or_create(utilisateur=utilisateur)
    solde.recalculer()
    return solde


def ajouter_credits(utilisateur, montant, type, note=""):
    if montant == 0:
        return None

    solde = assurer_solde_utilisateur(utilisateur)
    with transaction.atomic():
        transaction_obj = JournalCredits.objects.create(
            utilisateur=utilisateur,
            montant=int(montant),
            type=type,
            note=note,
        )
        solde.recalculer()
        return transaction_obj


def acheter_credits(utilisateur, montant, note=""):
    montant = int(montant)
    if montant <= 0:
        raise ValueError("Le montant de crédit doit être positif.")
    return ajouter_credits(
        utilisateur,
        montant,
        JournalCredits.Type.ACHAT_MANUEL,
        note or f"Achat de {montant} crédits",
    )


def debiter_pour_analyse(utilisateur, analyse, cout):
    if cout is None:
        configuration = analyse.configurations.first()
        cout = calculer_cout(
            {
                "type_audit": (
                    configuration.type_audit if configuration else TYPE_AUDIT_PAGE_UNIQUE
                ),
                "mode_analyse": (
                    configuration.mode_analyse if configuration else MODE_ANALYSE_RAPIDE
                ),
            },
            utilisateur,
        )

    cout = int(cout)
    if cout <= 0:
        return True
    if cout < 0:
        raise ValueError("Le coût ne peut pas être négatif.")

    solde = assurer_solde_utilisateur(utilisateur)
    total = JournalCredits.objects.filter(utilisateur=utilisateur).aggregate(
        total=Sum("montant")
    )["total"] or 0
    total = int(total)

    with transaction.atomic():
        if JournalCredits.objects.filter(
            utilisateur=utilisateur,
            analyse=analyse,
            type=JournalCredits.Type.DEBIT_ANALYSE,
        ).exists():
            return False

        if total < cout:
            return False

        try:
            JournalCredits.objects.create(
                utilisateur=utilisateur,
                analyse=analyse,
                montant=-cout,
                type=JournalCredits.Type.DEBIT_ANALYSE,
                note=f"Débit pour analyse {analyse.pk}",
            )
        except IntegrityError:
            return False

        solde.recalculer()
        return True


def rembourser_analyse(analyse):
    utilisateur = analyse.projet.utilisateur
    debit = (
        JournalCredits.objects.filter(
            utilisateur=utilisateur,
            analyse=analyse,
            type=JournalCredits.Type.DEBIT_ANALYSE,
        )
        .order_by("date")
        .first()
    )
    if debit is None or debit.montant >= 0:
        return False

    with transaction.atomic():
        if JournalCredits.objects.filter(
            utilisateur=utilisateur,
            analyse=analyse,
            type=JournalCredits.Type.REMBOURSEMENT,
        ).exists():
            return False

        montant = abs(int(debit.montant))
        if montant == 0:
            return False

        JournalCredits.objects.create(
            utilisateur=utilisateur,
            analyse=analyse,
            montant=montant,
            type=JournalCredits.Type.REMBOURSEMENT,
            note=f"Remboursement de l'analyse {analyse.pk}",
        )
        SoldeCredits.objects.get_or_create(utilisateur=utilisateur)[0].recalculer()
        return True


def attribuer_credits_bienvenue(utilisateur):
    if JournalCredits.objects.filter(
        utilisateur=utilisateur,
        type=JournalCredits.Type.BIENVENUE,
    ).exists():
        return None
    return ajouter_credits(
        utilisateur,
        CREDITS_BIENVENUE,
        JournalCredits.Type.BIENVENUE,
        "Crédits de bienvenue",
    )
