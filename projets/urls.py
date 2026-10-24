"""Adresses des projets."""

from django.urls import path

from . import views

urlpatterns = [
    path(
        "confidentialite/",
        views.politique_confidentialite,
        name="politique_confidentialite",
    ),
    path("", views.tableau_de_bord, name="tableau_de_bord"),
    path("projets/nouveau/", views.projet_creer, name="projet_creer"),
    path("projets/<int:pk>/", views.projet_detail, name="projet_detail"),
    path("projets/<int:pk>/modifier/", views.projet_modifier, name="projet_modifier"),
    path(
        "projets/<int:pk>/objectifs/ajouter/",
        views.objectif_creer,
        name="objectif_creer",
    ),
    path(
        "projets/<int:pk>/objectifs/<int:objectif_pk>/supprimer/",
        views.objectif_supprimer,
        name="objectif_supprimer",
    ),
]
