from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from credits.config import (
    COUT_PAGE_HORS_QUOTA,
    COUT_SITE_COMPLET_APPROFONDI,
    COUT_SITE_COMPLET_RAPIDE,
    CREDITS_BIENVENUE,
    PACKS_CREDITS,
    QUOTA_GRATUIT_MENSUEL,
    TEXTE_OBTENIR_CREDITS,
)
from credits.models import SoldeCredits
from credits.services import acheter_credits as acheter_credits_service, compter_analyses_gratuites_du_mois


def _libelle_transaction(transaction):
    libelles = {
        "bienvenue": "Crédits de bienvenue",
        "achat_manuel": "Achat manuel",
        "debit_analyse": "Débit pour une analyse",
        "remboursement": "Remboursement",
        "ajustement_admin": "Ajustement administratif",
    }
    return libelles.get(transaction.type, transaction.get_type_display())


def tarifs(request):
    prix_credit_reference = PACKS_CREDITS[0]["prix_par_credit"]
    couts_tarifs = [
        {
            "libelle": "Audit d'une page au-delà du quota",
            "credits": COUT_PAGE_HORS_QUOTA,
            "fcfa": COUT_PAGE_HORS_QUOTA * prix_credit_reference,
        },
        {
            "libelle": "Site complet rapide",
            "credits": COUT_SITE_COMPLET_RAPIDE,
            "fcfa": COUT_SITE_COMPLET_RAPIDE * prix_credit_reference,
        },
        {
            "libelle": "Site complet approfondi",
            "credits": COUT_SITE_COMPLET_APPROFONDI,
            "fcfa": COUT_SITE_COMPLET_APPROFONDI * prix_credit_reference,
        },
    ]
    return render(
        request,
        "credits/tarifs.html",
        {
            "packs_credits": PACKS_CREDITS,
            "couts_tarifs": couts_tarifs,
            "prix_credit_reference": prix_credit_reference,
            "credits_bienvenue": CREDITS_BIENVENUE,
            "quota_gratuit_mensuel": QUOTA_GRATUIT_MENSUEL,
            "texte_obtenir_credits": TEXTE_OBTENIR_CREDITS,
        },
    )


@login_required
def mes_credits(request):
    solde, _ = SoldeCredits.objects.get_or_create(utilisateur=request.user)
    solde.recalculer()
    transactions = list(request.user.credits_journal.order_by("date", "pk"))
    historique = []
    solde_courant = 0
    credits_recus = 0
    depenses = 0
    for transaction in transactions:
        solde_courant += transaction.montant
        if transaction.montant > 0:
            credits_recus += transaction.montant
        else:
            depenses += abs(transaction.montant)
        historique.append(
            {
                "date": transaction.date,
                "libelle": _libelle_transaction(transaction),
                "montant": transaction.montant,
                "note": transaction.note,
                "solde_apres": solde_courant,
                "type": transaction.type,
                "est_positif": transaction.montant >= 0,
            }
        )
    historique.reverse()

    gratuites_restantes = max(
        QUOTA_GRATUIT_MENSUEL - compter_analyses_gratuites_du_mois(request.user),
        0,
    )
    return render(
        request,
        "credits/mes_credits.html",
        {
            "solde": solde.solde,
            "gratuites_restantes": gratuites_restantes,
            "historique": historique,
            "credits_recus": credits_recus,
            "depenses": depenses,
            "dernier_mouvement": historique[0] if historique else None,
            "packs_credits": PACKS_CREDITS,
            "texte_obtenir_credits": TEXTE_OBTENIR_CREDITS,
            "quota_gratuit_mensuel": QUOTA_GRATUIT_MENSUEL,
        },
    )


@login_required
def acheter_credits(request):
    if request.method == "POST":
        try:
            montant = int(request.POST.get("montant", "0"))
        except (TypeError, ValueError):
            montant = 0

        if montant <= 0:
            messages.error(request, "Choisis un pack de crédits valide.")
            return redirect("acheter_credits")

        acheter_credits_service(request.user, montant, f"Achat de {montant} crédits")
        messages.success(request, f"Tu as acheté {montant} crédits. Ton solde a été mis à jour.")
        return redirect("mes_credits")

    solde, _ = SoldeCredits.objects.get_or_create(utilisateur=request.user)
    solde.recalculer()
    return render(
        request,
        "credits/acheter_credits.html",
        {
            "solde": solde.solde,
            "offres": PACKS_CREDITS,
        },
    )
