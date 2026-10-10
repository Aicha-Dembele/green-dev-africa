"""Crée un jeu de données de démonstration, pour voir le moteur en action.

    python manage.py creer_jeu_de_demo

La commande crée un projet de démonstration rattaché à ton compte, puis deux
analyses : une « avant » (site lourd) et une « après » (site optimisé). Elle
exécute les deux, les compare, et affiche le résultat dans le terminal.

Rejouable : le projet de démonstration est supprimé puis recréé à chaque fois.
Elle ne touche à aucun autre projet.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from analyses.indicateurs import unite_de
from analyses.models import (
    Analyse,
    ComparaisonAnalyse,
    Indicateur,
    RegleAnalyse,
    RessourceWeb,
)
from projets.models import ObjectifOptimisation, Projet

Utilisateur = get_user_model()

NOM_PROJET = "Démonstration — Portail d'actualités"

# Les mesures que l'outil d'audit déposera un jour tout seul.
# Clé = nom de l'indicateur = code de la règle qui le surveille.
#
# Le site « avant » casse 8 règles sur 10 : c'est ce qu'on observe sur un vrai
# site mal optimisé. S'il cassait les dix avec le maximum de gravité, le score
# tomberait à 0 et le taux d'amélioration ne voudrait plus rien dire (on ne
# divise pas par zéro). Les valeurs choisies font apparaître les quatre
# gravités, et les deux sortes de règles (plafond et comptage).
#
MESURES_AVANT = {
    "poids_total": 1850,            # max 500  -> x3,7  -> critique
    "poids_images": 650,            # max 300  -> x2,2  -> élevée
    "poids_javascript": 420,        # max 150  -> x2,8  -> élevée
    "nombre_requetes": 62,          # max 40   -> x1,55 -> moyenne
    "donnees_transferees": 1.9,     # max 1    -> x1,9  -> moyenne
    "temps_chargement": 4.2,        # max 3    -> x1,4  -> faible
    "images_non_optimisees": 4,     # comptage -> 4 cas -> moyenne
    "images_sans_alternative": 2,   # comptage -> 2 cas -> faible
    "poids_css": 45,                # sous le seuil
    "elements_dom": 620,            # sous le seuil
}

# Après optimisation : il reste volontairement un petit défaut de temps de
# chargement, pour que la démonstration ne soit pas trop belle.
MESURES_APRES = {
    "poids_total": 480,
    "poids_images": 210,
    "poids_javascript": 110,
    "temps_chargement": 3.4,        # max 3 -> x1,13 -> faible
    "nombre_requetes": 24,
    "donnees_transferees": 0.5,
    "poids_css": 38,
    "elements_dom": 540,
    "images_non_optimisees": 0,
    "images_sans_alternative": 0,
}

# Un échantillon des fichiers les plus lourds de la page « avant ».
# Les deux images totalisent bien les 650 Ko de l'indicateur poids_images.
RESSOURCES_AVANT = [
    ("banniere-accueil.png", RessourceWeb.Type.IMAGE, 380),
    ("photo-une.jpg", RessourceWeb.Type.IMAGE, 270),
    ("bundle.js", RessourceWeb.Type.SCRIPT, 420),
    ("police-titres.woff2", RessourceWeb.Type.POLICE, 60),
    ("style-complet.css", RessourceWeb.Type.STYLE, 45),
    ("index.html", RessourceWeb.Type.HTML, 45),
]


class Command(BaseCommand):
    help = "Crée un projet de démonstration avec deux analyses exécutées."

    def add_arguments(self, parseur):
        parseur.add_argument(
            "--utilisateur",
            help="Nom d'utilisateur à qui rattacher le projet "
            "(par défaut : le premier compte administrateur trouvé).",
        )

    def handle(self, *args, **options):
        if not RegleAnalyse.objects.filter(active=True).exists():
            raise CommandError(
                "Aucune règle active en base. Lance d'abord :\n"
                "    python manage.py charger_referentiel"
            )

        utilisateur = self._trouver_utilisateur(options.get("utilisateur"))
        self.stdout.write(f"Projet rattaché à : {utilisateur.username}")

        Projet.objects.filter(utilisateur=utilisateur, nom=NOM_PROJET).delete()
        projet = Projet.objects.create(
            utilisateur=utilisateur,
            nom=NOM_PROJET,
            description="Site d'actualités fictif, utilisé pour voir le moteur "
            "d'analyse fonctionner de bout en bout.",
            url="https://actualites.exemple.ml",
        )

        ObjectifOptimisation.objects.create(
            projet=projet,
            nom="Ramener la page d'accueil sous 500 Ko",
            valeur_cible=500,
            unite="Ko",
            date_limite=timezone.localdate() + timezone.timedelta(days=60),
        )

        avant = self._analyser(
            projet,
            MESURES_AVANT,
            ressources=RESSOURCES_AVANT,
            contexte={"qualite_connexion": "3g", "type_appareil": "mobile_bas"},
            quand=timezone.now() - timezone.timedelta(days=30),
            titre="AVANT optimisation",
        )
        apres = self._analyser(
            projet,
            MESURES_APRES,
            ressources=[],
            contexte={"qualite_connexion": "3g", "type_appareil": "mobile_bas"},
            quand=timezone.now(),
            titre="APRÈS optimisation",
        )

        comparaison = ComparaisonAnalyse.objects.create(
            analyse_avant=avant, analyse_apres=apres
        )
        comparaison.comparer_resultats()

        objectif = projet.objectifs.first()
        objectif.mettre_a_jour_progression(MESURES_APRES["poids_total"])

        self._afficher_bilan(projet, avant, apres, comparaison, objectif)

    # --- étapes ---

    def _trouver_utilisateur(self, nom_utilisateur):
        if nom_utilisateur:
            try:
                return Utilisateur.objects.get(username=nom_utilisateur)
            except Utilisateur.DoesNotExist:
                raise CommandError(f"Aucun compte « {nom_utilisateur} ».")
        utilisateur = (
            Utilisateur.objects.filter(is_superuser=True).order_by("id").first()
            or Utilisateur.objects.order_by("id").first()
        )
        if utilisateur is None:
            raise CommandError(
                "Aucun compte en base. Crée-le d'abord :\n"
                "    python manage.py createsuperuser"
            )
        return utilisateur

    def _analyser(self, projet, mesures, ressources, contexte, quand, titre):
        """Crée une analyse, dépose les mesures, puis l'exécute."""
        self.stdout.write(self.style.MIGRATE_HEADING(f"\n{titre}"))

        analyse = projet.lancer_analyse(
            configuration={"mode_analyse": "approfondi"}, contexte=contexte
        )
        analyse.date_analyse = quand
        analyse.save(update_fields=["date_analyse"])

        categories = dict(RegleAnalyse.objects.values_list("code", "categorie"))
        for nom, valeur in mesures.items():
            Indicateur.objects.create(
                analyse=analyse,
                nom=nom,
                valeur=valeur,
                unite=unite_de(nom),
                categorie=categories[nom],
            )

        for fichier, type_ressource, taille in ressources:
            ressource = RessourceWeb.objects.create(
                analyse=analyse,
                url=f"{projet.url}/static/{fichier}",
                type=type_ressource,
                taille=taille,
            )
            ressource.verifier_optimisation()

        analyse.executer_analyse()
        analyse.refresh_from_db()

        self.stdout.write(
            f"  Green Score : {analyse.score_global}/100 — "
            f"{analyse.problemes.count()} problème(s) détecté(s)"
        )
        for probleme in analyse.problemes.all():
            self.stdout.write(
                f"    [{probleme.get_gravite_display():>8}] {probleme.titre}"
            )
        return analyse

    def _afficher_bilan(self, projet, avant, apres, comparaison, objectif):
        self.stdout.write(self.style.MIGRATE_HEADING("\nCOMPARAISON"))
        # Le taux est incalculable si le score de départ était 0 : on l'affiche
        # alors en « — » plutôt que de faire planter la commande.
        taux = (
            f"{comparaison.taux_amelioration:+} %"
            if comparaison.taux_amelioration is not None
            else "taux incalculable (score de départ nul)"
        )
        self.stdout.write(
            f"  Score    : {comparaison.score_avant} → {comparaison.score_apres} "
            f"({comparaison.evolution:+} points, {taux})"
        )
        self.stdout.write(f"  Poids    : {comparaison.ecart_poids:+} Ko")
        self.stdout.write(
            f"  Objectif : {objectif.nom} → {objectif.get_statut_display()}"
        )

        contexte_avant = avant.contexte
        contexte_apres = apres.contexte
        self.stdout.write(self.style.MIGRATE_HEADING("\nCONTEXTE 3G / MOBILE MODESTE"))
        self.stdout.write(f"  Avant : {contexte_avant.proposer_optimisation()}")
        self.stdout.write(f"  Après : {contexte_apres.proposer_optimisation()}")

        recommandations = sum(
            p.recommandations.count()
            for analyse in (avant, apres)
            for p in analyse.problemes.all()
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"\nJeu de démonstration prêt : projet « {projet.nom} », "
                f"{Analyse.objects.filter(projet=projet).count()} analyses, "
                f"{recommandations} recommandations, 1 comparaison.\n"
                "Ouvre http://127.0.0.1:8000/admin/ pour tout voir."
            )
        )
