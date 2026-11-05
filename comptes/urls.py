"""Adresses des comptes.

Les noms donnés ici (`connexion`, `inscription`…) sont ceux qu'on écrit
dans les gabarits avec {% url 'connexion' %} : si l'adresse change un jour,
rien d'autre ne bouge.
"""

from django.conf import settings
from django.contrib.auth import views as vues_auth
from django.urls import path, reverse_lazy

from .forms import ConnexionForm, MotDePasseOublieForm, NouveauMotDePasseForm
from . import views

# Combien d'heures le lien « mot de passe oublié » reste valable. La vraie
# règle est PASSWORD_RESET_TIMEOUT dans settings.py ; on la transmet à
# l'e-mail et aux pages pour que le texte affiché dise toujours la même chose.
VALIDITE_LIEN = {"validite_heures": settings.PASSWORD_RESET_TIMEOUT // 3600}

urlpatterns = [
    path(
        "connexion/",
        vues_auth.LoginView.as_view(
            template_name="comptes/connexion.html",
            authentication_form=ConnexionForm,
        ),
        name="connexion",
    ),
    path("deconnexion/", vues_auth.LogoutView.as_view(), name="deconnexion"),
    # --- Mot de passe oublié : quatre pages toutes faites de Django ---
    # 1. On tape l'adresse e-mail de son compte.
    path(
        "mot-de-passe-oublie/",
        vues_auth.PasswordResetView.as_view(
            template_name="comptes/mot_de_passe_oublie.html",
            form_class=MotDePasseOublieForm,
            subject_template_name="comptes/email_mot_de_passe_sujet.txt",
            email_template_name="comptes/email_mot_de_passe.txt",
            extra_email_context=VALIDITE_LIEN,
            success_url=reverse_lazy("mot_de_passe_envoye"),
        ),
        name="mot_de_passe_oublie",
    ),
    # 2. On est invité à regarder sa boîte e-mail.
    path(
        "mot-de-passe-oublie/envoye/",
        vues_auth.PasswordResetDoneView.as_view(
            template_name="comptes/mot_de_passe_envoye.html",
            extra_context=VALIDITE_LIEN,
        ),
        name="mot_de_passe_envoye",
    ),
    # 3. Le lien reçu par e-mail ouvre cette page : on choisit le nouveau mot de passe.
    path(
        "nouveau-mot-de-passe/<uidb64>/<token>/",
        vues_auth.PasswordResetConfirmView.as_view(
            template_name="comptes/mot_de_passe_nouveau.html",
            form_class=NouveauMotDePasseForm,
            success_url=reverse_lazy("mot_de_passe_change"),
            extra_context=VALIDITE_LIEN,
        ),
        name="mot_de_passe_nouveau",
    ),
    # 4. C'est fait : un bouton ramène à la connexion.
    path(
        "nouveau-mot-de-passe/termine/",
        vues_auth.PasswordResetCompleteView.as_view(
            template_name="comptes/mot_de_passe_change.html",
        ),
        name="mot_de_passe_change",
    ),
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
