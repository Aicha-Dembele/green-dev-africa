"""Vues des comptes : inscription, profil, cloche de notifications.

La connexion et la déconnexion ne sont pas ici : Django les fournit
(`LoginView` et `LogoutView`), on les branche directement dans urls.py.
"""

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import InscriptionForm, ProfilForm
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
def profil(request):
    """Cas d'utilisation « Modifier son profil »."""
    maintenant = timezone.now()

    if request.method == "POST":
        formulaire = ProfilForm(request.POST, instance=request.user)
        if formulaire.is_valid():
            if formulaire.has_changed():
                utilisateur = formulaire.save(commit=False)
                utilisateur.profil_modifie_le = maintenant
                utilisateur.save()
                request.user.refresh_from_db()
            messages.success(request, "Profil mis à jour.")
            return redirect("profil")
    else:
        formulaire = ProfilForm(instance=request.user)

    return render(
        request,
        "comptes/profil.html",
        {
            "formulaire": formulaire,
        },
    )


@login_required
def notifications(request):
    """La liste complète derrière la cloche."""
    return render(
        request,
        "comptes/notifications.html",
        {"notifications": request.user.notifications.all()},
    )


@login_required
def notification_lue(request, pk):
    """Marque une notification comme lue, puis revient là d'où on vient.

    On filtre sur `utilisateur=request.user` : personne ne peut toucher
    la notification de quelqu'un d'autre, même en devinant son numéro.
    """
    notification = get_object_or_404(Notification, pk=pk, utilisateur=request.user)
    if request.method == "POST":
        notification.marquer_comme_lue()
    return redirect(request.POST.get("retour") or "notifications")


@login_required
def notifications_toutes_lues(request):
    """Vide la cloche d'un seul coup."""
    if request.method == "POST":
        request.user.notifications.filter(lu=False).update(lu=True)
        messages.success(request, "Toutes les notifications sont marquées comme lues.")
    return redirect("notifications")
