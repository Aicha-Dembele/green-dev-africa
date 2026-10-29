from django.core.management.base import BaseCommand
from django.db.models import Sum

from comptes.models import Utilisateur
from credits.models import JournalCredits, SoldeCredits


class Command(BaseCommand):
    help = "Vérifie que chaque solde correspond à la somme du journal et signale les soldes manquants."

    def handle(self, *args, **options):
        utilisateurs = Utilisateur.objects.all().order_by("username", "pk")
        avertissements = 0
        erreurs = 0

        for utilisateur in utilisateurs:
            solde = SoldeCredits.objects.filter(utilisateur=utilisateur).first()
            total_journal = (
                JournalCredits.objects.filter(utilisateur=utilisateur).aggregate(
                    total=Sum("montant")
                )["total"]
                or 0
            )
            total_journal = int(total_journal)

            if solde is None:
                self.stdout.write(
                    self.style.WARNING(
                        f"AVERTISSEMENT {utilisateur} ({utilisateur.pk}) : solde absent | journal={total_journal}"
                    )
                )
                avertissements += 1
                continue

            diff = solde.solde - total_journal
            if diff == 0:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"OK  {utilisateur} : solde={solde.solde} | journal={total_journal}"
                    )
                )
            else:
                self.stdout.write(
                    self.style.ERROR(
                        f"ERREUR {utilisateur} : solde={solde.solde} | journal={total_journal} | diff={diff}"
                    )
                )
                erreurs += 1

        if avertissements == 0 and erreurs == 0:
            self.stdout.write(
                self.style.SUCCESS("Tous les soldes sont cohérents et aucun solde manquant n'a été détecté.")
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"{avertissements} avertissement(s) de solde absent et {erreurs} erreur(s) de solde incohérent."
                )
            )
