"""Adresses des analyses."""

from django.urls import path

from . import views

urlpatterns = [
    # Lancer et consulter
    path(
        "projets/<int:pk>/analyser/",
        views.lancer_analyse,
        name="lancer_analyse",
    ),
    path("analyses/<int:pk>/", views.analyse_detail, name="analyse_detail"),
    path(
        "recommandations/<int:pk>/faite/",
        views.recommandation_faite,
        name="recommandation_faite",
    ),
    path(
        "problemes/<int:pk>/statut/",
        views.probleme_statut,
        name="probleme_statut",
    ),
    # Rapport
    path("analyses/<int:pk>/rapport/", views.rapport_detail, name="rapport_detail"),
    path("analyses/<int:pk>/rapport.json", views.rapport_json, name="rapport_json"),
    path(
        "analyses/<int:pk>/rapport/partager/",
        views.rapport_partager,
        name="rapport_partager",
    ),
    path(
        "partages/<int:pk>/revoquer/",
        views.partage_revoquer,
        name="partage_revoquer",
    ),
    # La seule adresse publique : le lien de partage.
    path("r/<str:jeton>/", views.rapport_public, name="rapport_public"),
    # Comparaison
    path("projets/<int:pk>/comparer/", views.comparer, name="comparer"),
    path(
        "comparaisons/<int:pk>/",
        views.comparaison_detail,
        name="comparaison_detail",
    ),
    # Administration des règles
    path("regles/", views.regles_seuils, name="regles_seuils"),
]
