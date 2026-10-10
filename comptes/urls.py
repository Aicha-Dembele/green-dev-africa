"""Adresses des comptes.

Les noms donnés ici (`connexion`, `inscription`…) sont ceux qu'on écrit
dans les gabarits avec {% url 'connexion' %} : si l'adresse change un jour,
rien d'autre ne bouge.
"""

from django.contrib.auth import views as vues_auth
from django.urls import path

from . import views

urlpatterns = [
    path(
        "connexion/",
        vues_auth.LoginView.as_view(template_name="comptes/connexion.html"),
        name="connexion",
    ),
    path("deconnexion/", vues_auth.LogoutView.as_view(), name="deconnexion"),
    path("inscription/", views.inscription, name="inscription"),
    path("profil/", views.profil, name="profil"),
    path("notifications/", views.notifications, name="notifications"),
    path(
        "notifications/<int:pk>/lue/",
        views.notification_lue,
        name="notification_lue",
    ),
    path(
        "notifications/toutes-lues/",
        views.notifications_toutes_lues,
        name="notifications_toutes_lues",
    ),
]
