"""Modele a recopier sous le nom config/local_settings.py.

Ce fichier-ci est publie ; local_settings.py ne l'est jamais (voir .gitignore).

Pour generer ta propre cle secrete :

    python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
"""

SECRET_KEY = "colle-ici-ta-cle-secrete"
DEBUG = True
