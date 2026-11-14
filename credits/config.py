CREDITS_BIENVENUE = 10
QUOTA_GRATUIT_MENSUEL = 5

PRIX_CREDIT_FCFA = 50
ACHAT_MINIMUM_FCFA = 1000
ACHAT_PAS_FCFA = 500
ACHAT_MAXIMUM_FCFA = 50000
MONTANTS_SUGGERES = [1000, 2500, 5000]

# Les packs affichés sur la page Tarifs et à l'étape 1 de l'achat. Le prix
# du crédit reste le même partout : un pack n'est qu'un montant conseillé.
PACKS = [
    {
        "code": "decouverte",
        "nom": "Découverte",
        "montant": 1000,
        "accroche": "Pour tester un site complet ou deux.",
        "populaire": False,
    },
    {
        "code": "essentiel",
        "nom": "Essentiel",
        "montant": 2500,
        "accroche": "Pour suivre un site dans le temps.",
        "populaire": True,
    },
    {
        "code": "pro",
        "nom": "Pro",
        "montant": 5000,
        "accroche": "Pour les agences et plusieurs projets.",
        "populaire": False,
    },
]

# Moyens de paiement proposés dans la simulation (aucun n'est réellement
# appelé). « famille » décide des champs demandés à l'étape 2.
MOYENS_PAIEMENT = [
    {"code": "orange_money", "nom": "Orange Money", "famille": "mobile"},
    {"code": "wave", "nom": "Wave", "famille": "mobile"},
    {"code": "moov_money", "nom": "Moov Money", "famille": "mobile"},
    {"code": "carte", "nom": "Carte bancaire", "famille": "carte"},
]

INDICATIFS = [
    ("+223", "Mali (+223)"),
    ("+221", "Sénégal (+221)"),
    ("+225", "Côte d'Ivoire (+225)"),
    ("+226", "Burkina Faso (+226)"),
    ("+224", "Guinée (+224)"),
    ("+227", "Niger (+227)"),
    ("+228", "Togo (+228)"),
    ("+229", "Bénin (+229)"),
    ("+237", "Cameroun (+237)"),
]

# Mode test : seules ces cartes sont acceptées, pour ne jamais faire saisir
# une vraie carte. La seconde simule un refus de la banque.
CARTE_TEST_ACCEPTEE = "4242424242424242"
CARTE_TEST_REFUSEE = "4000000000000002"
# Un numéro mobile qui se termine ainsi simule un solde insuffisant.
SUFFIXE_TELEPHONE_REFUSE = "0000"

DUREE_VALIDITE_COMMANDE_MINUTES = 30
TENTATIVES_CODE_MAX = 3

COUT_PAGE_HORS_QUOTA = 1
COUT_SITE_COMPLET_RAPIDE = 5
COUT_SITE_COMPLET_APPROFONDI = 10

TEXTE_OBTENIR_CREDITS = (
    "Le paiement est simulé : aucun montant ne sera prélevé. Les crédits sont ajoutés "
    "à ton solde après la validation du paiement."
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
