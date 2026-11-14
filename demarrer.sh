#!/bin/sh
# Démarrage du conteneur de production.
# set -e : si une étape échoue (base injoignable, migration ratée), le
# conteneur s'arrête avec l'erreur dans les logs au lieu de servir un site
# dont les tables n'existent pas.
set -e

echo "[demarrage] Base utilisée :"
python manage.py shell -c "from django.db import connection as c; s=c.settings_dict; print('  moteur =', s['ENGINE']); print('  hote   =', s.get('HOST')); print('  port   =', s.get('PORT')); print('  base   =', s.get('NAME'))"

echo "[demarrage] Application des migrations…"
python manage.py migrate --noinput

echo "[demarrage] Vérification : aucune migration ne doit rester en attente."
python manage.py migrate --check

echo "[demarrage] Chargement du référentiel d'analyse…"
python manage.py charger_referentiel

echo "[demarrage] Collecte des fichiers statiques…"
python manage.py collectstatic --noinput

# Une analyse s'exécute pendant la requête et peut durer plus d'une minute
# (jusqu'à 10 pages, 10 s de délai par fichier) : le délai par défaut de
# gunicorn (30 s) tuerait le worker en pleine analyse. Plusieurs workers et
# threads évitent qu'une analyse en cours bloque tous les autres visiteurs.
# Surcharge possible via GUNICORN_WORKERS, GUNICORN_THREADS, GUNICORN_TIMEOUT.
echo "[demarrage] Lancement de gunicorn sur le port ${PORT:-8000}"
exec gunicorn config.wsgi:application \
    --bind "0.0.0.0:${PORT:-8000}" \
    --workers "${GUNICORN_WORKERS:-2}" \
    --threads "${GUNICORN_THREADS:-4}" \
    --timeout "${GUNICORN_TIMEOUT:-180}" \
    --access-logfile -
