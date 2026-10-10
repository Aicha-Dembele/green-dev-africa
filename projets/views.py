"""Vues des projets : le tableau de bord et la fiche d'un projet.

Règle de sécurité appliquée partout dans ce fichier : on ne cherche jamais un
projet par son seul numéro, toujours avec `utilisateur=request.user`. Un
visiteur qui change le numéro dans l'adresse obtient une page 404, pas le
projet de quelqu'un d'autre.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, OuterRef, Q, Subquery
from django.shortcuts import get_object_or_404, redirect, render

from analyses.models import Analyse, ProblemeDetecte

from .forms import ObjectifForm, ProjetForm
from .models import Projet


@login_required
def tableau_de_bord(request):
    """Cas d'utilisation « Consulter le tableau de bord ».

    Tout est calculé en trois requêtes : les sous-requêtes `Subquery` vont
    chercher la dernière analyse de chaque projet sans refaire un appel à la
    base par ligne affichée.
    """
    derniere = Analyse.objects.filter(projet=OuterRef("pk")).order_by("-date_analyse")

    projets = request.user.projets.annotate(
        nb_analyses=Count("analyses", distinct=True),
        derniere_analyse_id=Subquery(derniere.values("id")[:1]),
        dernier_score=Subquery(derniere.values("score_global")[:1]),
        derniere_date=Subquery(derniere.values("date_analyse")[:1]),
    )

    problemes = ProblemeDetecte.objects.filter(
        analyse__projet__utilisateur=request.user
    ).aggregate(
        ouverts=Count("pk", filter=Q(statut=ProblemeDetecte.Statut.OUVERT)),
        critiques=Count(
            "pk",
            filter=Q(
                statut=ProblemeDetecte.Statut.OUVERT,
                gravite=ProblemeDetecte.Gravite.CRITIQUE,
            ),
        ),
    )

    scores = [p.dernier_score for p in projets if p.dernier_score is not None]

    return render(
        request,
        "projets/tableau_de_bord.html",
        {
            "projets": projets,
            "nb_projets": len(projets),
            "score_moyen": round(sum(scores) / len(scores), 1) if scores else None,
            "problemes_ouverts": problemes["ouverts"],
            "problemes_critiques": problemes["critiques"],
        },
    )


@login_required
def projet_creer(request):
    """Cas d'utilisation « Créer un projet »."""
    if request.method == "POST":
        formulaire = ProjetForm(request.POST)
        if formulaire.is_valid():
            projet = formulaire.save(commit=False)
            # Le propriétaire n'est pas dans le formulaire : il vient de la
            # session, sinon n'importe qui pourrait créer un projet au nom
            # d'un autre en modifiant la page.
            projet.utilisateur = request.user
            projet.save()
            messages.success(request, f"Projet « {projet.nom} » créé.")
            return redirect("projet_detail", pk=projet.pk)
    else:
        formulaire = ProjetForm()

    return render(
        request,
        "projets/projet_form.html",
        {"formulaire": formulaire, "titre": "Nouveau projet"},
    )


@login_required
def projet_modifier(request, pk):
    projet = get_object_or_404(Projet, pk=pk, utilisateur=request.user)

    if request.method == "POST":
        formulaire = ProjetForm(request.POST, instance=projet)
        if formulaire.is_valid():
            formulaire.save()
            messages.success(request, "Projet mis à jour.")
            return redirect("projet_detail", pk=projet.pk)
    else:
        formulaire = ProjetForm(instance=projet)

    return render(
        request,
        "projets/projet_form.html",
        {"formulaire": formulaire, "projet": projet, "titre": f"Modifier {projet.nom}"},
    )


@login_required
def projet_detail(request, pk):
    """La fiche d'un projet : son historique d'analyses et ses objectifs."""
    projet = get_object_or_404(Projet, pk=pk, utilisateur=request.user)

    analyses = projet.consulter_historique().annotate(
        nb_problemes=Count("problemes", distinct=True)
    )

    return render(
        request,
        "projets/projet_detail.html",
        {
            "projet": projet,
            "analyses": analyses,
            "objectifs": projet.objectifs.all(),
            "formulaire_objectif": ObjectifForm(),
        },
    )


@login_required
def objectif_creer(request, pk):
    """Ajoute un objectif depuis la fiche du projet."""
    projet = get_object_or_404(Projet, pk=pk, utilisateur=request.user)

    if request.method == "POST":
        formulaire = ObjectifForm(request.POST)
        if formulaire.is_valid():
            objectif = formulaire.save(commit=False)
            objectif.projet = projet
            objectif.save()
            messages.success(request, f"Objectif « {objectif.nom} » ajouté.")
            return redirect("projet_detail", pk=projet.pk)
        messages.error(request, "L'objectif n'a pas pu être enregistré.")
        return render(
            request,
            "projets/projet_detail.html",
            {
                "projet": projet,
                "analyses": projet.consulter_historique(),
                "objectifs": projet.objectifs.all(),
                "formulaire_objectif": formulaire,
            },
        )

    return redirect("projet_detail", pk=projet.pk)


@login_required
def objectif_supprimer(request, pk, objectif_pk):
    projet = get_object_or_404(Projet, pk=pk, utilisateur=request.user)
    objectif = get_object_or_404(projet.objectifs, pk=objectif_pk)

    if request.method == "POST":
        objectif.delete()
        messages.success(request, "Objectif supprimé.")

    return redirect("projet_detail", pk=projet.pk)
