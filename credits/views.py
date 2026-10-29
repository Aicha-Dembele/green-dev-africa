from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from credits.config import QUOTA_GRATUIT_MENSUEL
from credits.models import SoldeCredits
from credits.services import compter_analyses_gratuites_du_mois


def _libelle_transaction(transaction):
    libelles = {
        "bienvenue": "Crédits de bienvenue",
        "achat_manuel": "Achat manuel",
        "debit_analyse": "Débit pour une analyse",
        "remboursement": "Remboursement",
        "ajustement_admin": "Ajustement administratif",
    }
    return libelles.get(transaction.type, transaction.get_type_display())


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
        },
    )
