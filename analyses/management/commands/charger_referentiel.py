"""Remplit les deux tables de paramétrage de Green Dev Africa.

À lancer une fois après la création de la base :

    python manage.py charger_referentiel

Sans ce référentiel, une analyse ne détecte rien : les règles sont ce à quoi
on compare les mesures, et les conseils sont ce qu'on affiche en face.
La commande est rejouable : elle met à jour au lieu de dupliquer.
"""

from django.core.management.base import BaseCommand

from analyses.models import ConseilOptimisation, RegleAnalyse

Categorie = RegleAnalyse.Categorie

# Le code de la règle est le nom de l'indicateur qu'elle surveille.
REGLES = [
    {
        "code": "poids_total",
        "categorie": Categorie.POIDS,
        "seuil": 500,
        "description": "Le poids total de la page dépasse 500 Ko, ce qui la rend "
        "lente et coûteuse à charger sur un forfait data limité.",
    },
    {
        "code": "nombre_requetes",
        "categorie": Categorie.REQUETES,
        "seuil": 40,
        "description": "La page déclenche plus de 40 requêtes réseau : chaque "
        "requête ajoute un aller-retour, très pénalisant en 3G.",
    },
    {
        "code": "temps_chargement",
        "categorie": Categorie.RESEAU,
        "seuil": 3,
        "description": "La page met plus de 3 secondes à s'afficher ; au-delà, "
        "une grande partie des visiteurs abandonne.",
    },
    {
        "code": "donnees_transferees",
        "categorie": Categorie.POIDS,
        "seuil": 1,
        "description": "La visite consomme plus de 1 Mo de données, soit une part "
        "sensible d'un petit forfait mobile.",
    },
    {
        "code": "poids_images",
        "categorie": Categorie.IMAGES,
        "seuil": 300,
        "description": "Les images pèsent plus de 300 Ko au total : c'est "
        "presque toujours le premier poste d'économie d'un site.",
    },
    {
        "code": "images_non_optimisees",
        "categorie": Categorie.IMAGES,
        "seuil": 0,
        "description": "Des images sont servies sans compression ni format "
        "moderne (WebP / AVIF) ni redimensionnement.",
    },
    {
        "code": "poids_javascript",
        "categorie": Categorie.CODE,
        "seuil": 150,
        "description": "Le JavaScript dépasse 150 Ko : il doit être téléchargé, "
        "analysé puis exécuté, ce qui épuise les téléphones modestes.",
    },
    {
        "code": "poids_css",
        "categorie": Categorie.CODE,
        "seuil": 60,
        "description": "La feuille de style dépasse 60 Ko, souvent parce qu'on "
        "charge un cadre complet pour n'en utiliser qu'une petite partie.",
    },
    {
        "code": "elements_dom",
        "categorie": Categorie.CODE,
        "seuil": 800,
        "description": "La page contient plus de 800 éléments HTML, ce qui rend "
        "l'affichage et le défilement laborieux.",
    },
    {
        "code": "images_sans_alternative",
        "categorie": Categorie.ACCESSIBILITE,
        "seuil": 0,
        "description": "Des images n'ont pas de texte alternatif : la page est "
        "inutilisable pour un lecteur d'écran et quand les images ne chargent pas.",
    },
]

# Les exemples de code des conseils. Ils sont volontairement courts et
# copiables tels quels : un pavé de quarante lignes ne serait jamais lu, et
# ne tiendrait pas dans le PDF. Ils sont affichés sans coloration ni
# interprétation — on ne promet pas qu'ils marchent dans tous les contextes,
# on montre la forme que prend la correction.

EXEMPLE_POIDS = """\
# nginx : compresser les réponses texte avant de les envoyer
gzip on;
gzip_types text/css application/javascript application/json image/svg+xml;
gzip_min_length 1024;"""

EXEMPLE_REQUETES = """\
<!-- Avant : trois fichiers, trois allers-retours sur le réseau -->
<link rel="stylesheet" href="base.css">
<link rel="stylesheet" href="grille.css">
<link rel="stylesheet" href="boutons.css">

<!-- Après : un seul fichier, un seul aller-retour -->
<link rel="stylesheet" href="site.css">"""

EXEMPLE_IMAGES = """\
<picture>
  <source srcset="photo.avif" type="image/avif">
  <source srcset="photo.webp" type="image/webp">
  <img src="photo.jpg" alt="Marché de Bamako"
       width="800" height="600" loading="lazy">
</picture>"""

EXEMPLE_CODE = """\
<!-- defer : le script n'empêche plus la page de s'afficher -->
<script src="app.js" defer></script>

// et ne charger la grosse brique que si on s'en sert
bouton.addEventListener("click", async () => {
  const { afficherCarte } = await import("./carte.js");
  afficherCarte();
});"""

EXEMPLE_RESEAU = """\
# nginx : un an de cache pour les fichiers dont le nom change à chaque version
location /static/ {
  add_header Cache-Control "public, max-age=31536000, immutable";
}"""

EXEMPLE_ACCESSIBILITE = """\
<!-- Image porteuse de sens : décrire ce qu'elle apporte -->
<img src="graphique.png" alt="Trafic en hausse de 12 % en 2026">

<!-- Image purement décorative : alt vide, et non alt absent -->
<img src="separateur.svg" alt="">"""


# Un conseil par catégorie : c'est la fiche rattachée aux recommandations.
CONSEILS = [
    {
        "categorie": Categorie.POIDS,
        "titre": "Alléger le poids de la page",
        "explication": "Chaque kilo-octet envoyé est de l'électricité dépensée et "
        "du forfait consommé chez le visiteur. Une page sobre tient sous 500 Ko.",
        "solution_technique": "Compresser les réponses (gzip ou brotli), supprimer "
        "les bibliothèques inutilisées, charger les contenus lourds seulement "
        "quand l'utilisateur en a besoin.",
        "exemple_code": EXEMPLE_POIDS,
        "gain_attendu": "30 à 60 % de poids en moins",
    },
    {
        "categorie": Categorie.REQUETES,
        "titre": "Réduire le nombre de requêtes",
        "explication": "Sur un réseau mobile, le temps perdu vient surtout des "
        "allers-retours, pas de la taille des fichiers.",
        "solution_technique": "Regrouper les fichiers CSS et JS, utiliser des "
        "sprites ou des icônes en SVG, supprimer les traceurs et widgets externes.",
        "exemple_code": EXEMPLE_REQUETES,
        "gain_attendu": "moitié des requêtes en moins",
    },
    {
        "categorie": Categorie.IMAGES,
        "titre": "Optimiser les images",
        "explication": "Les images représentent en général plus de la moitié du "
        "poids d'une page, pour un gain visuel souvent invisible.",
        "solution_technique": "Redimensionner aux dimensions réellement affichées, "
        "convertir en WebP ou AVIF, activer le chargement différé (loading=\"lazy\").",
        "exemple_code": EXEMPLE_IMAGES,
        "gain_attendu": "jusqu'à 70 % du poids des images",
    },
    {
        "categorie": Categorie.CODE,
        "titre": "Dégraisser le code JavaScript et CSS",
        "explication": "Le code non utilisé est téléchargé, lu et exécuté quand "
        "même : c'est la partie la plus coûteuse pour un téléphone d'entrée de gamme.",
        "solution_technique": "Minifier, supprimer le code mort, remplacer les "
        "gros cadres par du code natif, découper par page (code splitting).",
        "exemple_code": EXEMPLE_CODE,
        "gain_attendu": "40 à 70 % de code en moins",
    },
    {
        "categorie": Categorie.RESEAU,
        "titre": "Mettre en cache et rapprocher les fichiers",
        "explication": "Un fichier déjà en cache ne repart pas sur le réseau : "
        "la deuxième visite devient presque gratuite.",
        "solution_technique": "Déclarer des en-têtes Cache-Control longs sur les "
        "fichiers statiques, servir depuis un hébergement proche des visiteurs, "
        "activer HTTP/2.",
        "exemple_code": EXEMPLE_RESEAU,
        "gain_attendu": "1 à 3 secondes de chargement en moins",
    },
    {
        "categorie": Categorie.ACCESSIBILITE,
        "titre": "Rendre la page lisible sans les images",
        "explication": "Un texte alternatif sert au lecteur d'écran, mais aussi à "
        "tout visiteur dont les images n'ont pas chargé faute de réseau.",
        "solution_technique": "Renseigner l'attribut alt de chaque image porteuse "
        "de sens, garder un contraste suffisant, ne pas dépendre de la couleur seule.",
        "exemple_code": EXEMPLE_ACCESSIBILITE,
        "gain_attendu": "page utilisable même sans images",
    },
]


class Command(BaseCommand):
    help = "Charge les règles d'analyse et les conseils d'optimisation."

    def handle(self, *args, **options):
        for modele in REGLES:
            # On travaille sur une copie : sinon on viderait REGLES et la
            # commande ne pourrait plus être rejouée.
            donnees = dict(modele)
            code = donnees.pop("code")
            _, cree = RegleAnalyse.objects.update_or_create(
                code=code, defaults=donnees
            )
            self.stdout.write(f"  {'+ ' if cree else '= '}règle {code}")

        for modele in CONSEILS:
            donnees = dict(modele)
            titre = donnees.pop("titre")
            _, cree = ConseilOptimisation.objects.update_or_create(
                titre=titre, defaults=donnees
            )
            self.stdout.write(f"  {'+ ' if cree else '= '}conseil « {titre} »")

        self.stdout.write(
            self.style.SUCCESS(
                f"\nRéférentiel chargé : {RegleAnalyse.objects.count()} règles, "
                f"{ConseilOptimisation.objects.count()} conseils."
            )
        )
