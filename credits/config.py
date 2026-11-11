CREDITS_BIENVENUE = 10
QUOTA_GRATUIT_MENSUEL = 5

PRIX_CREDIT_FCFA = 50
ACHAT_MINIMUM_FCFA = 1000
ACHAT_PAS_FCFA = 500
ACHAT_MAXIMUM_FCFA = 50000
MONTANTS_SUGGERES = [1000, 2500, 5000]

COUT_PAGE_HORS_QUOTA = 1
COUT_SITE_COMPLET_RAPIDE = 5
COUT_SITE_COMPLET_APPROFONDI = 10

TEXTE_OBTENIR_CREDITS = (
    "Le paiement est simulé : aucun montant ne sera prélevé. Les crédits sont ajoutés "
    "à ton solde après ta confirmation."
)

TYPE_AUDIT_PAGE_UNIQUE = "page_unique"
TYPE_AUDIT_SITE_COMPLET = "site_complet"
MODE_ANALYSE_RAPIDE = "rapide"
MODE_ANALYSE_APPROFONDI = "approfondi"


def credits_pour_montant(montant_fcfa: int) -> int:
    if not isinstance(montant_fcfa, int) or isinstance(montant_fcfa, bool):
        raise ValueError("Le montant doit être un nombre entier de FCFA.")
    if montant_fcfa < ACHAT_MINIMUM_FCFA:
        raise ValueError(f"Le montant minimum est de {ACHAT_MINIMUM_FCFA} FCFA.")
    if montant_fcfa > ACHAT_MAXIMUM_FCFA:
        raise ValueError(f"Le montant maximum est de {ACHAT_MAXIMUM_FCFA} FCFA.")
    if (montant_fcfa - ACHAT_MINIMUM_FCFA) % ACHAT_PAS_FCFA != 0:
        raise ValueError(f"Le montant doit avancer par pas de {ACHAT_PAS_FCFA} FCFA.")
    return montant_fcfa // PRIX_CREDIT_FCFA


def montant_pour_credits(credits: int) -> int:
    return credits * PRIX_CREDIT_FCFA
