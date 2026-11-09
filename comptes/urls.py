"""Adresses des comptes.

Les noms donnés ici (`connexion`, `inscription`…) sont ceux qu'on écrit
dans les gabarits avec {% url 'connexion' %} : si l'adresse change un jour,
rien d'autre ne bouge.
"""

from django.contrib.auth import views as vues_auth
from django.urls import path, reverse_lazy

from .forms import ConnexionForm
from . import views

urlpatterns = [
    path(
        "connexion/",
        vues_auth.LoginView.as_view(
            template_name="comptes/connexion.html",
            authentication_form=ConnexionForm,
        ),
        name="connexion",
    ),
    path(
        "mot-de-passe-oublie/",
        vues_auth.PasswordResetView.as_view(
            template_name="comptes/mot_de_passe_oublie.html",
            email_template_name="comptes/email/mot_de_passe_oublie.txt",
            success_url=reverse_lazy("mot_de_passe_oublie_envoye"),
        ),
        name="mot_de_passe_oublie",
    ),
    path(
        "mot-de-passe-oublie/envoye/",
        vues_auth.PasswordResetDoneView.as_view(
            template_name="comptes/mot_de_passe_oublie_envoye.html"
        ),
        name="mot_de_passe_oublie_envoye",
    ),
    path(
        "reinitialiser/<uidb64>/<token>/",
        vues_auth.PasswordResetConfirmView.as_view(
            template_name="comptes/mot_de_passe_reinitialiser.html",
            success_url=reverse_lazy("mot_de_passe_reinitialisee"),
        ),
        name="mot_de_passe_reinitialiser",
    ),
    path(
        "reinitialiser/terminee/",
        vues_auth.PasswordResetCompleteView.as_view(
            template_name="comptes/mot_de_passe_reinitialisee.html"
        ),
        name="mot_de_passe_reinitialisee",
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
