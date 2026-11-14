#!/bin/sh
# Démarrage du conteneur. Les migrations et le référentiel sont appliqués par
# gunicorn.conf.py, lu automatiquement par gunicorn quelle que soit la
# commande qui le lance. Commande de démarrage la plus simple sur Systalink :
#     gunicorn config.wsgi:application

echo "[demarrage] Collecte des fichiers statiques…"
# Non bloquant : si le dossier n'est pas accessible en écriture, WhiteNoise
# sert les fichiers depuis les sources (WHITENOISE_USE_FINDERS).
python manage.py collectstatic --noinput \
    || echo "[demarrage] collectstatic impossible, fichiers servis depuis les sources."

exec gunicorn config.wsgi:application
