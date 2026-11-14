#!/bin/sh
# Démarrage du conteneur (Dockerfile). Les migrations et le référentiel sont
# appliqués par gunicorn.conf.py, lu automatiquement par gunicorn quelle que
# soit la commande qui le lance : ce script ne fait que les fichiers statiques.
set -e

echo "[demarrage] Collecte des fichiers statiques…"
python manage.py collectstatic --noinput

exec gunicorn config.wsgi:application
