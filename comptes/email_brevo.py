"""Envoi des e-mails par l'API HTTPS de Brevo (https://www.brevo.com).

Pourquoi l'API plutôt que le SMTP de Brevo ? Les hébergeurs gratuits bloquent
souvent les ports SMTP sortants (25, 465, 587) ; une requête HTTPS passe
toujours. Django ne voit qu'un « backend » e-mail comme un autre : les vues
(mot de passe oublié…) n'ont rien à savoir de Brevo.

Activation : définir BREVO_API_KEY dans l'environnement (voir settings.py).
L'adresse DEFAULT_FROM_EMAIL doit être un expéditeur validé dans Brevo
(menu « Expéditeurs, domaines et IP dédiées »), sinon Brevo refuse l'envoi.
"""

import logging
from email.utils import getaddresses, parseaddr

import requests
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

journal = logging.getLogger(__name__)

URL_API = "https://api.brevo.com/v3/smtp/email"


class ErreurBrevo(Exception):
    """Brevo a refusé le message, ou n'a pas pu être joint."""


def _contact(adresse):
    """« Nom <a@b.c> » → {"email": "a@b.c", "name": "Nom"} (format Brevo)."""
    nom, email = parseaddr(adresse)
    contact = {"email": email}
    if nom:
        contact["name"] = nom
    return contact


def _contacts(adresses):
    return [
        {"email": email, **({"name": nom} if nom else {})}
        for nom, email in getaddresses(adresses)
    ]


class BrevoEmailBackend(BaseEmailBackend):
    def __init__(self, fail_silently=False, api_key=None, timeout=None, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        self.api_key = api_key or getattr(settings, "BREVO_API_KEY", "")
        self.timeout = timeout or getattr(settings, "EMAIL_TIMEOUT", None) or 10

    def send_messages(self, email_messages):
        envoyes = 0
        for message in email_messages:
            try:
                self._envoyer(message)
            except Exception:
                journal.exception("Envoi Brevo impossible (sujet : %s)", message.subject)
                if not self.fail_silently:
                    raise
            else:
                envoyes += 1
        return envoyes

    def _corps(self, message):
        donnees = {
            "sender": _contact(message.from_email or settings.DEFAULT_FROM_EMAIL),
            "to": _contacts(message.to),
            "subject": message.subject,
            "textContent": message.body,
        }
        if message.cc:
            donnees["cc"] = _contacts(message.cc)
        if message.bcc:
            donnees["bcc"] = _contacts(message.bcc)
        if message.reply_to:
            donnees["replyTo"] = _contact(message.reply_to[0])
        for contenu, type_mime in getattr(message, "alternatives", None) or []:
            if type_mime == "text/html":
                donnees["htmlContent"] = contenu
        return donnees

    def _envoyer(self, message):
        if not self.api_key:
            raise ErreurBrevo("BREVO_API_KEY n'est pas définie.")
        if not message.recipients():
            return
        try:
            reponse = requests.post(
                URL_API,
                json=self._corps(message),
                headers={
                    "api-key": self.api_key,
                    "accept": "application/json",
                    "content-type": "application/json",
                },
                timeout=self.timeout,
            )
        except requests.RequestException as erreur:
            raise ErreurBrevo(f"Brevo injoignable : {erreur}") from erreur
        if reponse.status_code >= 300:
            # Le corps de la réponse explique la cause (clé invalide,
            # expéditeur non validé…) ; il ne contient pas la clé.
            raise ErreurBrevo(
                f"Brevo a refusé l'e-mail ({reponse.status_code}) : {reponse.text[:300]}"
            )
