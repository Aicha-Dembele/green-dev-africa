"""Exécute en arrière-plan les analyses en attente.

Lancer un seul processus de cette commande à côté du serveur Django :
    python manage.py traiter_analyses
"""

import logging
import time

from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections

from analyses.collecteur import ErreurCollecte
from analyses.models import Analyse

journal = logging.getLogger(__name__)


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
            close_old_connections()
            analyse = self._prendre_analyse()
            if analyse is None:
                if options["once"]:
                    return
                time.sleep(interval)
                continue

            try:
                analyse.executer_analyse()
            except ErreurCollecte as erreur:
                analyse.message_erreur = str(erreur)
                analyse.save(update_fields=["message_erreur"])
                self.stderr.write(
                    self.style.ERROR(f"Analyse {analyse.pk} échouée : {erreur}")
                )
            except Exception:
                journal.exception("Échec du traitement de l'analyse %s", analyse.pk)
                analyse.message_erreur = (
                    "Une erreur inattendue a empêché l'analyse. Réessaie plus tard."
                )
                analyse.save(update_fields=["message_erreur"])
                self.stderr.write(
                    self.style.ERROR(f"Analyse {analyse.pk} échouée.")
                )
            else:
                self.stdout.write(self.style.SUCCESS(f"Analyse {analyse.pk} terminée."))
            close_old_connections()

            if options["once"]:
                return

    @staticmethod
    def _prendre_analyse():
        attente = Analyse.Statut.EN_ATTENTE
        identifiants = Analyse.objects.filter(statut=attente).order_by(
            "date_analyse", "pk"
        ).values_list("pk", flat=True)[:1]
        for identifiant in identifiants:
            reservee = Analyse.objects.filter(pk=identifiant, statut=attente).update(
                statut=Analyse.Statut.EN_COURS
            )
            if reservee:
                return Analyse.objects.get(pk=identifiant)
        return None
