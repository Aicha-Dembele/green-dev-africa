"""Envoie un e-mail de test pour vérifier la configuration d'envoi.

    python manage.py tester_email moi@exemple.com

Affiche le service utilisé et, en cas d'échec, la raison donnée par le
fournisseur (clé invalide, expéditeur non validé…).
"""

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Envoie un e-mail de test à l'adresse donnée."

    def add_arguments(self, parser):
        parser.add_argument("destinataire")

    def handle(self, *args, destinataire, **options):
        self.stdout.write(f"Service : {settings.EMAIL_BACKEND}")
        self.stdout.write(f"Expéditeur : {settings.DEFAULT_FROM_EMAIL}")
        try:
            send_mail(
                "Green Dev Africa : e-mail de test",
                "Si tu lis ce message, l'envoi d'e-mails fonctionne.",
                None,
                [destinataire],
            )
        except Exception as erreur:
            raise CommandError(f"Échec de l'envoi : {erreur}") from erreur
        self.stdout.write(self.style.SUCCESS(f"E-mail envoyé à {destinataire}."))
