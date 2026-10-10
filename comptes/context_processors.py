"""Données disponibles dans tous les gabarits, sans que chaque vue les passe.

Un « context processor » est une fonction appelée à chaque affichage de page :
ce qu'elle renvoie s'ajoute au contexte de tous les gabarits. C'est ce qui
permet d'avoir la pastille de la cloche partout, y compris sur les pages dont
la vue ne parle pas de notifications.

Il est branché dans `config/settings.py`, section TEMPLATES.
"""


def notifications_non_lues(request):
    utilisateur = getattr(request, "user", None)
    if utilisateur is None or not utilisateur.is_authenticated:
        return {}
    return {
        "notifications_non_lues": utilisateur.notifications.filter(lu=False).count()
    }
