from django.core.management.base import BaseCommand

from comptes.models import Utilisateur
from credits.config import CREDITS_BIENVENUE
from credits.models import JournalCredits, SoldeCredits
from credits.services import ajouter_credits


class Command(BaseCommand):
    help = "Crée les soldes manquants et attribue les crédits de bienvenue une seule fois, avec support --dry-run."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Affiche les actions qui seraient entreprises sans rien écrire en base.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        utilisateurs = list(Utilisateur.objects.order_by("pk"))
        actions = []

        for utilisateur in utilisateurs:
            solde_existe = SoldeCredits.objects.filter(utilisateur=utilisateur).exists()
            if not solde_existe:
                actions.append(
                    f"Crée le solde pour {utilisateur} ({utilisateur.pk}) : {CREDITS_BIENVENUE}"
                )

            if not JournalCredits.objects.filter(
                utilisateur=utilisateur,
                type=JournalCredits.Type.BIENVENUE,
            ).exists():
                actions.append(
                    f"Attribuer les crédits de bienvenue à {utilisateur} ({utilisateur.pk}) : {CREDITS_BIENVENUE}"
                )

        if not actions:
            self.stdout.write(
                self.style.SUCCESS(
                    "Aucune action nécessaire : tous les soldes et crédits de bienvenue sont déjà cohérents."
                )
            )
            return

        if dry_run:
            self.stdout.write(self.style.WARNING("--dry-run : aucune écriture, voici ce qui serait fait :"))
            for action in actions:
                self.stdout.write(f"- {action}")
            return

        for utilisateur in utilisateurs:
            solde, _ = SoldeCredits.objects.get_or_create(utilisateur=utilisateur)
            solde.recalculer()
            if not JournalCredits.objects.filter(
                utilisateur=utilisateur,
                type=JournalCredits.Type.BIENVENUE,
            ).exists():
                ajouter_credits(
                    utilisateur,
                    CREDITS_BIENVENUE,
                    JournalCredits.Type.BIENVENUE,
                    "Crédits de bienvenue",
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Initialisation des crédits terminée pour {len(utilisateurs)} utilisateur(s)."
            )
        )
