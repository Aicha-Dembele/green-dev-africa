"""Exécute en arrière-plan les analyses en attente.

Lancer un seul processus de cette commande à côté du serveur Django :
    python manage.py traiter_analyses
"""

import logging
import time
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections
from django.utils import timezone

from analyses.collecteur import ErreurCollecte
from analyses.models import Analyse

journal = logging.getLogger(__name__)


# Une analyse ne peut pas durer plus longtemps que le délai de gunicorn
# (quelques minutes). Au-delà, son processus a été tué (redémarrage,
# dépassement de délai) : sans ce filet, elle resterait « En cours » pour
# toujours et bloquerait le projet.
DUREE_MAX_ANALYSE = timedelta(minutes=15)


def liberer_analyses_bloquees(utilisateur=None):
    """Passe en « Échouée » (et rembourse) les analyses abandonnées en cours."""
    from credits.services import rembourser_analyse

    limite = timezone.now() - DUREE_MAX_ANALYSE
    bloquees = Analyse.objects.filter(
        statut__in=[Analyse.Statut.EN_COURS, Analyse.Statut.EN_ATTENTE],
        date_analyse__lt=limite,
    )
    if utilisateur is not None:
        bloquees = bloquees.filter(projet__utilisateur=utilisateur)

    liberees = 0
    for analyse in bloquees.select_related("projet__utilisateur"):
        mises_a_jour = Analyse.objects.filter(
            pk=analyse.pk, statut=analyse.statut
        ).update(
            statut=Analyse.Statut.ECHOUEE,
            message_erreur=(
                "L'analyse a été interrompue avant la fin. Tu peux la relancer."
            ),
        )
        if mises_a_jour:
            rembourser_analyse(analyse)
            journal.warning("Analyse %s interrompue : marquée échouée.", analyse.pk)
            liberees += 1
    return liberees


def traiter_une_analyse_en_attente(utilisateur=None):
    """Traite la première analyse en attente et la ressort en sortie.

    L'objectif est de centraliser le cœur du worker pour qu'il puisse être
    réutilisé par les vues Django quand aucune commande externe n'est lancée.
    """
    close_old_connections()
    analyse = Command._prendre_analyse(utilisateur=utilisateur)
    if analyse is None:
        return None

    try:
        analyse.executer_analyse()
    except ErreurCollecte as erreur:
        analyse.message_erreur = str(erreur)
        analyse.save(update_fields=["message_erreur"])
        journal.error("Analyse %s échouée : %s", analyse.pk, erreur)
        return analyse
    except Exception:
        journal.exception("Échec du traitement de l'analyse %s", analyse.pk)
        analyse.message_erreur = (
            "Une erreur inattendue a empêché l'analyse. Réessaie plus tard."
        )
        analyse.save(update_fields=["message_erreur"])
        return analyse
    else:
        return analyse
    finally:
        close_old_connections()


class Command(BaseCommand):
    help = "Traite en arrière-plan les analyses en attente."

    def add_arguments(self, parser):
        parser.add_argument(
            "--interval",
            type=float,
            default=2,
            help="Délai en secondes entre les vérifications de la file.",
        )
        parser.add_argument(
            "--once",
            action="store_true",
            help="Traite au plus une analyse puis quitte.",
        )

    def handle(self, *args, **options):
        interval = options["interval"]
        if interval <= 0:
            raise CommandError("--interval doit être supérieur à zéro.")

        while True:
            analyse = traiter_une_analyse_en_attente()
            if analyse is None:
                if options["once"]:
                    return
                time.sleep(interval)
                continue

            if analyse.statut == Analyse.Statut.TERMINEE:
                self.stdout.write(self.style.SUCCESS(f"Analyse {analyse.pk} terminée."))
            elif analyse.statut == Analyse.Statut.ECHOUEE:
                self.stderr.write(
                    self.style.ERROR(f"Analyse {analyse.pk} échouée : {analyse.message_erreur}")
                )

            if options["once"]:
                return

    @staticmethod
    def _prendre_analyse(utilisateur=None):
        attente = Analyse.Statut.EN_ATTENTE
        analyses = Analyse.objects.filter(statut=attente)
        if utilisateur is not None:
            analyses = analyses.filter(projet__utilisateur=utilisateur)

        identifiants = analyses.order_by("date_analyse", "pk").values_list(
            "pk", flat=True
        )[:1]
        for identifiant in identifiants:
            reservee = Analyse.objects.filter(pk=identifiant, statut=attente).update(
                statut=Analyse.Statut.EN_COURS
            )
            if reservee:
                return Analyse.objects.get(pk=identifiant)
        return None
