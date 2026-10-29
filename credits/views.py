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
    transactions = list(request.user.credits_journal.order_by("date", "pk"))
    historique = []
    solde_courant = 0
    for transaction in transactions:
        solde_courant += transaction.montant
        historique.append(
            {
                "date": transaction.date,
                "libelle": _libelle_transaction(transaction),
                "montant": transaction.montant,
                "note": transaction.note,
                "solde_apres": solde_courant,
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
        },
    )
