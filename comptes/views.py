"""Vues des comptes : inscription, profil, cloche de notifications.

La connexion et la déconnexion ne sont pas ici : Django les fournit
(`LoginView` et `LogoutView`), on les branche directement dans urls.py.
"""

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_POST

from .forms import InscriptionForm
from .models import Notification


def inscription(request):
    """Cas d'utilisation « Créer un compte », puis connexion automatique."""
    if request.method == "POST":
        formulaire = InscriptionForm(request.POST)
        if formulaire.is_valid():
            utilisateur = formulaire.save()
            login(request, utilisateur)
            messages.success(
                request, f"Bienvenue {utilisateur} ! Crée ton premier projet."
            )
            return redirect("tableau_de_bord")
    else:
        formulaire = InscriptionForm()

    return render(request, "comptes/inscription.html", {"formulaire": formulaire})


@login_required
@require_GET
def profil(request):
    """Affiche les informations en lecture seule du compte connecté."""
    return render(request, "comptes/profil.html")


@login_required
def notifications(request):
    """La liste complète derrière la cloche."""
    return render(
        request,
        "comptes/notifications.html",
        {"notifications": request.user.notifications.all()},
    )


@login_required
@require_POST
def notification_lue(request, pk):
    """Marque une notification comme lue, puis revient là d'où on vient.

    On filtre sur `utilisateur=request.user` : personne ne peut toucher
    la notification de quelqu'un d'autre, même en devinant son numéro.
    """
    notification = get_object_or_404(Notification, pk=pk, utilisateur=request.user)
    notification.marquer_comme_lue()
    retour = request.POST.get("retour", "")
    if not url_has_allowed_host_and_scheme(
        retour, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        retour = ""
    return redirect(retour or "notifications")


@login_required
@require_POST
def notifications_toutes_lues(request):
    """Vide la cloche d'un seul coup."""
    request.user.notifications.filter(lu=False).update(lu=True)
    messages.success(request, "Toutes les notifications sont marquées comme lues.")
    return redirect("notifications")
