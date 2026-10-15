"""Vues des analyses : lancement, consultation, rapport, partage, comparaison.

Deux règles appliquées partout :

1. **Cloisonnement** — on ne charge jamais un objet par son seul numéro. On
   remonte toujours jusqu'au propriétaire (`projet__utilisateur=request.user`),
   si bien que changer le numéro dans l'adresse donne une 404.
2. **Les écritures passent par POST** — marquer une recommandation comme
   faite, partager un rapport ou révoquer un lien modifient la base : un
   simple clic sur un lien (GET) ne doit jamais pouvoir le faire.

Seule exception à la règle 1 : la page publique d'un rapport partagé, qui
s'ouvre sans compte mais exige un jeton valide.
"""

import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.forms import modelformset_factory
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from projets.models import Projet

from .collecteur import ErreurCollecte
from .forms import ComparaisonForm, LancerAnalyseForm
from .models import (
    Analyse,
    ComparaisonAnalyse,
    Indicateur,
    PartageRapport,
    ProblemeDetecte,
    Rapport,
    Recommandation,
    RegleAnalyse,
)

journal = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
#  Raccourcis de chargement : ils portent le cloisonnement des données
# ---------------------------------------------------------------------------


def _projet_de(request, pk):
    return get_object_or_404(Projet, pk=pk, utilisateur=request.user)


def _analyse_de(request, pk, requete=None):
    return get_object_or_404(
        requete if requete is not None else Analyse.objects.all(),
        pk=pk,
        projet__utilisateur=request.user,
    )


# ---------------------------------------------------------------------------
#  Lancer et consulter une analyse
# ---------------------------------------------------------------------------


@login_required
def lancer_analyse(request, pk):
    """Cas d'utilisation « Lancer une analyse d'une URL »."""
    projet = _projet_de(request, pk)

    if not RegleAnalyse.objects.filter(active=True).exists():
        messages.error(
            request,
            "Aucune règle d'analyse active : demande à un administrateur d'en "
            "activer, sinon il n'y a rien à vérifier.",
        )
        return redirect("projet_detail", pk=projet.pk)

    if request.method == "POST":
        formulaire = LancerAnalyseForm(request.POST)
        if formulaire.is_valid():
            analyse = projet.lancer_analyse(
                configuration=formulaire.configuration(),
                contexte=formulaire.contexte(),
            )

            # Un seul aller-retour vers la base pour toutes les mesures.
            Indicateur.objects.bulk_create(
                Indicateur(analyse=analyse, **mesure)
                for mesure in formulaire.mesures()
            )

            try:
                analyse.executer_analyse()
            except ErreurCollecte as erreur:
                # Le site n'a pas pu être mesuré : le message vient du
                # collecteur, il est écrit pour l'utilisateur.
                messages.error(request, f"Mesure impossible — {erreur}")
                return redirect("analyse_detail", pk=analyse.pk)
            except Exception:
                # On trace l'erreur côté serveur, mais on ne montre pas une
                # page de plantage : l'analyse reste visible, en statut
                # « Échouée », et l'utilisateur peut recommencer.
                journal.exception("Échec de l'analyse %s", analyse.pk)
                messages.error(
                    request,
                    "L'analyse n'a pas pu aller jusqu'au bout. Elle est "
                    "enregistrée comme échouée.",
                )
                return redirect("analyse_detail", pk=analyse.pk)

            messages.success(
                request,
                f"Analyse terminée : Green Score {analyse.score_global:g}/100 "
                f"({analyse.indicateurs.count()} mesures, "
                f"{analyse.ressources.count()} fichiers pesés).",
            )
            return redirect("analyse_detail", pk=analyse.pk)
    else:
        formulaire = LancerAnalyseForm()

    return render(
        request,
        "analyses/lancer_analyse.html",
        {"projet": projet, "formulaire": formulaire},
    )


@login_required
def analyse_detail(request, pk):
    """Cas d'utilisation « Consulter le tableau de bord et les problèmes »."""
    analyse = _analyse_de(
        request,
        pk,
        Analyse.objects.select_related("projet", "contexte", "rapport"),
    )

    problemes = analyse.problemes.select_related("regle", "ressource").prefetch_related(
        "recommandations__conseil"
    )
    contexte = getattr(analyse, "contexte", None)

    # On calcule la part de chaque ressource ici, une fois, plutôt que
    # d'appeler `calculer_poids()` depuis le gabarit : la méthode du modèle
    # fait une somme en base, ce qui donnerait une requête par ligne affichée.
    ressources = list(analyse.ressources.all())
    poids_cumule = sum(ressource.taille for ressource in ressources)
    for ressource in ressources:
        ressource.part = (
            round(ressource.taille * 100 / poids_cumule, 1) if poids_cumule else 0
        )

    return render(
        request,
        "analyses/analyse_detail.html",
        {
            "analyse": analyse,
            "problemes": problemes,
            "indicateurs": analyse.indicateurs.all(),
            "ressources": ressources,
            "configuration": analyse.configurations.first(),
            "contexte": contexte,
            "verdict_contexte": contexte.proposer_optimisation() if contexte else None,
            "compatible": contexte.evaluer_compatibilite() if contexte else None,
            "rapport": getattr(analyse, "rapport", None),
            "statuts_probleme": ProblemeDetecte.Statut.choices,
        },
    )


@login_required
def recommandation_faite(request, pk):
    """Le développeur coche une recommandation qu'il a appliquée."""
    recommandation = get_object_or_404(
        Recommandation,
        pk=pk,
        probleme__analyse__projet__utilisateur=request.user,
    )

    if request.method == "POST":
        recommandation.marquer_comme_faite()
        messages.success(request, "Recommandation marquée comme faite.")

    return redirect("analyse_detail", pk=recommandation.probleme.analyse_id)


@login_required
def probleme_statut(request, pk):
    """Le développeur suit l'avancement d'un problème."""
    probleme = get_object_or_404(
        ProblemeDetecte, pk=pk, analyse__projet__utilisateur=request.user
    )

    if request.method == "POST":
        statut = request.POST.get("statut")
        if statut in ProblemeDetecte.Statut.values:
            probleme.changer_statut(statut)
            messages.success(request, f"Problème : {probleme.get_statut_display()}.")
        else:
            messages.error(request, "Statut inconnu.")

    return redirect("analyse_detail", pk=probleme.analyse_id)


# ---------------------------------------------------------------------------
#  Rapport : consultation, export, partage
# ---------------------------------------------------------------------------


@login_required
def rapport_detail(request, pk):
    """Cas d'utilisation « Générer un rapport »."""
    analyse = _analyse_de(request, pk, Analyse.objects.select_related("projet"))
    rapport = getattr(analyse, "rapport", None)

    if rapport is None:
        messages.error(
            request,
            "Cette analyse n'a pas encore de rapport : exécute-la d'abord.",
        )
        return redirect("analyse_detail", pk=analyse.pk)

    return render(
        request,
        "analyses/rapport.html",
        {
            "rapport": rapport,
            "analyse": analyse,
            "problemes": analyse.problemes.select_related(
                "regle", "ressource"
            ).prefetch_related("recommandations__conseil"),
            "partages": rapport.partages.all(),
            "public": False,
        },
    )


@login_required
def rapport_json(request, pk):
    """exporterJSON() du diagramme, servi comme fichier téléchargeable."""
    analyse = _analyse_de(request, pk)
    rapport = getattr(analyse, "rapport", None)
    if rapport is None:
        messages.error(request, "Cette analyse n'a pas encore de rapport.")
        return redirect("analyse_detail", pk=analyse.pk)

    reponse = JsonResponse(rapport.exporter_json(), json_dumps_params={"indent": 2})
    reponse["Content-Disposition"] = (
        f'attachment; filename="green-dev-rapport-{analyse.pk}.json"'
    )
    return reponse


@login_required
def rapport_pdf(request, pk):
    """genererPDF() du diagramme, servi comme fichier téléchargeable.

    Même cloisonnement que partout : `_analyse_de` ne trouve l'analyse que si
    elle appartient à l'utilisateur connecté. Changer le numéro dans l'adresse
    donne une 404, pas le rapport du voisin.
    """
    analyse = _analyse_de(request, pk, Analyse.objects.select_related("projet"))
    rapport = getattr(analyse, "rapport", None)
    if rapport is None:
        messages.error(request, "Cette analyse n'a pas encore de rapport.")
        return redirect("analyse_detail", pk=analyse.pk)

    reponse = HttpResponse(rapport.generer_pdf(), content_type="application/pdf")
    reponse["Content-Disposition"] = (
        f'attachment; filename="green-dev-rapport-{analyse.pk}.pdf"'
    )
    return reponse


@login_required
def rapport_partager(request, pk):
    """Cas d'utilisation « Partager le rapport par un lien public »."""
    analyse = _analyse_de(request, pk)
    rapport = get_object_or_404(Rapport, analyse=analyse)

    if request.method == "POST":
        duree = request.POST.get("duree_jours")
        try:
            duree = max(1, min(int(duree), 365))
        except (TypeError, ValueError):
            duree = 30

        partage = rapport.partager(duree_jours=duree)
        lien = request.build_absolute_uri(
            reverse("rapport_public", args=[partage.jeton])
        )
        messages.success(
            request,
            f"Lien public créé, valable {duree} jours : {lien}",
        )

    return redirect("rapport_detail", pk=analyse.pk)


@login_required
def partage_revoquer(request, pk):
    """Coupe un lien public avant son expiration."""
    partage = get_object_or_404(
        PartageRapport,
        pk=pk,
        rapport__analyse__projet__utilisateur=request.user,
    )

    if request.method == "POST":
        partage.revoquer_lien()
        messages.success(request, "Lien révoqué : il ne s'ouvre plus.")

    return redirect("rapport_detail", pk=partage.rapport.analyse_id)


def rapport_public(request, jeton):
    """La page qu'ouvre le destinataire du lien. Sans compte, mais avec jeton.

    C'est la seule vue accessible sans connexion. Le jeton est tiré au hasard
    sur 32 octets : on ne tombe pas dessus en changeant un chiffre.
    """
    partage = get_object_or_404(
        PartageRapport.objects.select_related("rapport__analyse__projet"), jeton=jeton
    )

    if not partage.verifier_validite():
        # 410 Gone : la ressource a existé, elle n'est plus disponible.
        return render(request, "analyses/rapport_indisponible.html", status=410)

    analyse = partage.rapport.analyse
    return render(
        request,
        "analyses/rapport.html",
        {
            "rapport": partage.rapport,
            "analyse": analyse,
            "problemes": analyse.problemes.select_related(
                "regle", "ressource"
            ).prefetch_related("recommandations__conseil"),
            "partage": partage,
            "public": True,
        },
    )


# ---------------------------------------------------------------------------
#  Comparaison avant / après
# ---------------------------------------------------------------------------


@login_required
def comparer(request, pk):
    """Cas d'utilisation « Comparer deux analyses (avant / après) »."""
    projet = _projet_de(request, pk)

    if request.method == "POST":
        formulaire = ComparaisonForm(projet, request.POST)
        if formulaire.is_valid():
            comparaison = ComparaisonAnalyse.objects.create(
                analyse_avant=formulaire.cleaned_data["analyse_avant"],
                analyse_apres=formulaire.cleaned_data["analyse_apres"],
            )
            comparaison.comparer_resultats()
            return redirect("comparaison_detail", pk=comparaison.pk)
    else:
        formulaire = ComparaisonForm(projet)

    return render(
        request,
        "analyses/comparer.html",
        {
            "projet": projet,
            "formulaire": formulaire,
            "comparaisons": ComparaisonAnalyse.objects.filter(
                analyse_avant__projet=projet
            ).select_related("analyse_avant", "analyse_apres"),
        },
    )


@login_required
def comparaison_detail(request, pk):
    comparaison = get_object_or_404(
        ComparaisonAnalyse.objects.select_related(
            "analyse_avant__projet", "analyse_apres__projet"
        ),
        pk=pk,
        analyse_avant__projet__utilisateur=request.user,
    )

    return render(
        request,
        "analyses/comparaison_detail.html",
        {
            "comparaison": comparaison,
            "projet": comparaison.analyse_avant.projet,
            # Recalculés à l'affichage : les indicateurs et les problèmes des
            # deux analyses sont déjà en base, les figer une seconde fois
            # n'apporterait qu'un risque de désaccord entre les deux copies.
            "indicateurs": comparaison.comparer_indicateurs(),
            "bilan": comparaison.bilan_problemes(),
        },
    )


# ---------------------------------------------------------------------------
#  Réservé à l'administrateur
# ---------------------------------------------------------------------------


@login_required
def regles_seuils(request):
    """Cas d'utilisation « Régler les seuils des règles d'analyse ».

    Un `modelformset` affiche une ligne modifiable par règle : Django
    s'occupe de valider et d'enregistrer les lignes modifiées.
    """
    if not (request.user.is_superuser or request.user.est_administrateur()):
        raise PermissionDenied(
            "Seuls les administrateurs peuvent régler les seuils des règles."
        )

    FormSet = modelformset_factory(
        RegleAnalyse, fields=("seuil", "active"), extra=0
    )
    requete = RegleAnalyse.objects.order_by("categorie", "code")

    if request.method == "POST":
        formset = FormSet(request.POST, queryset=requete)
        if formset.is_valid():
            formset.save()
            messages.success(request, "Seuils enregistrés.")
            return redirect("regles_seuils")
    else:
        formset = FormSet(queryset=requete)

    return render(request, "analyses/regles_seuils.html", {"formset": formset})
