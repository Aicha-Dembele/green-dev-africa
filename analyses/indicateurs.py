"""Le catalogue des indicateurs : une seule source de vérité.

Chaque indicateur y est décrit une fois — son intitulé lisible, son unité et
sa catégorie — et tout le reste du projet lit ce catalogue : le formulaire de
saisie, le collecteur automatique et la commande de démonstration.

Le `code` est la clé qui relie trois choses :
  - le `nom` d'un Indicateur enregistré en base,
  - le `code` de la RegleAnalyse qui le surveille,
  - la clé renvoyée par le collecteur.

Les catégories sont écrites en clair plutôt qu'importées de RegleAnalyse :
ce module doit rester lisible sans charger les modèles. Un test vérifie
qu'elles correspondent bien aux catégories existantes.
"""

#: code -> (intitulé, unité, catégorie)
CATALOGUE = {
    "poids_total": ("Poids total de la page", "Ko", "poids"),
    "donnees_transferees": ("Données transférées", "Mo", "poids"),
    "nombre_requetes": ("Nombre de requêtes", "requêtes", "requetes"),
    # Vaut 1 pour un audit d'une seule page, davantage en « site complet » :
    # il dit sur combien de pages les moyennes ont été faites. Aucune règle
    # ne le surveille, il est là pour informer.
    "nombre_pages": ("Pages analysées", "pages", "requetes"),
    "temps_chargement": ("Temps de chargement", "s", "reseau"),
    "poids_images": ("Poids des images", "Ko", "images"),
    "images_non_optimisees": ("Images non optimisées", "images", "images"),
    "poids_javascript": ("Poids du JavaScript", "Ko", "code"),
    "poids_css": ("Poids des feuilles de style", "Ko", "code"),
    "elements_dom": ("Nombre d'éléments HTML", "éléments", "code"),
    "images_sans_alternative": (
        "Images sans texte alternatif",
        "images",
        "accessibilite",
    ),
}

#: Indicateurs qui décrivent l'analyse sans porter de jugement. Les comparer
#: « en mieux » ou « en moins bien » n'aurait aucun sens : passer de 1 à 5
#: pages analysées n'est ni un progrès ni une régression.
INFORMATIFS = {"nombre_pages"}


def libelle_de(code):
    """L'intitulé à afficher à l'utilisateur."""
    if code in CATALOGUE:
        return CATALOGUE[code][0]
    return code.replace("_", " ").capitalize()


def unite_de(code):
    """L'unité de mesure (« Ko », « s », « requêtes »…)."""
    return CATALOGUE[code][1] if code in CATALOGUE else ""


def categorie_de(code, defaut="code"):
    """La catégorie de la règle qui surveille cet indicateur."""
    return CATALOGUE[code][2] if code in CATALOGUE else defaut


def est_informatif(code):
    """Cet indicateur se compare-t-il en mieux / moins bien ?"""
    return code in INFORMATIFS
