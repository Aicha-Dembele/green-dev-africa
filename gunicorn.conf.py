"""Configuration de gunicorn, chargée automatiquement depuis la racine du projet.

Gunicorn lit ce fichier tout seul, quelle que soit la commande qui le lance
(Dockerfile, plateforme d'hébergement, terminal). C'est donc ici qu'on garantit
que la base est prête avant d'accepter la moindre requête : sans migrations,
le site s'affiche mais toute page qui lit la base répond « erreur 500 ».

Les options passées en ligne de commande restent prioritaires sur celles-ci.
"""

import os

# Une analyse s'exécute pendant la requête et peut durer plus d'une minute
# (jusqu'à 10 pages, 10 s de délai par fichier) : le délai par défaut (30 s)
# tuerait le worker en pleine analyse. Les threads évitent qu'une analyse en
# cours bloque les autres visiteurs.
bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"
workers = int(os.environ.get("GUNICORN_WORKERS", "2"))
threads = int(os.environ.get("GUNICORN_THREADS", "4"))
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "180"))
accesslog = "-"


def on_starting(server):
    """Avant de lancer les workers : afficher la base, migrer, charger les règles.

    S'exécute une seule fois, dans le processus principal. En cas d'échec,
    l'exception arrête gunicorn : mieux vaut un déploiement en échec, visible
    dans les logs, qu'un site en ligne sans tables.
    """
    if os.environ.get("GUNICORN_SANS_MIGRATION") == "True":
        server.log.info("[demarrage] Migrations ignorées (GUNICORN_SANS_MIGRATION).")
        return

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django

    django.setup()

    from django.core.management import call_command
    from django.db import connection, connections

    reglages = connection.settings_dict
    server.log.info(
        "[demarrage] Base : %s hote=%s port=%s nom=%s",
        reglages["ENGINE"],
        reglages.get("HOST"),
        reglages.get("PORT"),
        reglages.get("NAME"),
    )

    server.log.info("[demarrage] Application des migrations…")
    call_command("migrate", interactive=False, verbosity=1)
    call_command("migrate", check=True, verbosity=0)

    server.log.info("[demarrage] Chargement du référentiel d'analyse…")
    call_command("charger_referentiel", verbosity=0)

    # Les workers sont créés par fork : ils ne doivent pas hériter de la
    # connexion ouverte ici.
    connections.close_all()
    server.log.info("[demarrage] Base prête.")
