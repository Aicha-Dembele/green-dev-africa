from django.urls import path

from . import views

urlpatterns = [
    path("mes-credits/", views.mes_credits, name="mes_credits"),
    # Parcours d'achat : montant → paiement → confirmation → reçu.
    path("acheter/", views.acheter_credits, name="acheter_credits"),
    path(
        "commande/<str:reference>/paiement/",
        views.commande_paiement,
        name="commande_paiement",
    ),
    path(
        "commande/<str:reference>/confirmation/",
        views.commande_confirmation,
        name="commande_confirmation",
    ),
    path("commande/<str:reference>/recu/", views.commande_recu, name="commande_recu"),
    path("commande/<str:reference>/echec/", views.commande_echec, name="commande_echec"),
    path(
        "commande/<str:reference>/annuler/",
        views.commande_annuler,
        name="commande_annuler",
    ),
]
