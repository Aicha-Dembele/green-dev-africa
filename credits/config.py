CREDITS_BIENVENUE = 10
QUOTA_GRATUIT_MENSUEL = 5

PACKS_CREDITS = [
    {"label": "Essai", "prix": 1000, "credits": 10, "montant": 10},
    {"label": "Pro", "prix": 5000, "credits": 70, "montant": 70},
]

for pack in PACKS_CREDITS:
    pack["prix_par_credit"] = pack["prix"] / pack["credits"]

OFFRES_CREDITS = PACKS_CREDITS

COUT_PAGE_HORS_QUOTA = 1
COUT_SITE_COMPLET_RAPIDE = 5
COUT_SITE_COMPLET_APPROFONDI = 10

TEXTE_OBTENIR_CREDITS = (
    "Le paiement par mobile money arrive bientôt. "
    "Pour l'instant, contactez-nous pour recharger vos crédits : [TON MOYEN DE CONTACT]."
)

TYPE_AUDIT_PAGE_UNIQUE = "page_unique"
TYPE_AUDIT_SITE_COMPLET = "site_complet"
MODE_ANALYSE_RAPIDE = "rapide"
MODE_ANALYSE_APPROFONDI = "approfondi"
