# Green Dev Africa — back-end

Application web d'analyse de la sobriété numérique d'un site (projet CADEV 2026).

Le back-end suit le **diagramme de classes** du projet : les 16 classes du
diagramme sont devenues 16 modèles Django, répartis en trois applications.

## Où est quoi

| Application | Classes du diagramme |
|---|---|
| `comptes` | Utilisateur, Notification |
| `projets` | Projet, ObjectifOptimisation |
| `analyses` | Analyse, ConfigurationAnalyse, UtilisateurContexte, Indicateur, RessourceWeb, RegleAnalyse, ProblemeDetecte, Recommandation, ConseilOptimisation, Rapport, PartageRapport, ComparaisonAnalyse |

Fichiers à connaître :

- `comptes/models.py`, `projets/models.py`, `analyses/models.py` — les modèles,
  avec en commentaire la relation du diagramme dont ils viennent.
- `*/views.py`, `*/forms.py`, `*/urls.py` — les pages du site.
- `templates/` — les gabarits HTML ; `static/css/greendev.css` — tout le style.
- `analyses/collecteur.py` — **l'outil d'audit** : télécharge la page et ses
  fichiers, et en tire les mesures. Ne connaît ni Django ni la base.
- `analyses/indicateurs.py` — le catalogue des indicateurs (intitulé, unité,
  catégorie), source unique lue par le formulaire, le collecteur et la démo.
- `analyses/management/commands/charger_referentiel.py` — les règles d'analyse
  et les conseils d'optimisation (le paramétrage du moteur).
- `analyses/tests.py` (moteur), `analyses/tests_vues.py`, `projets/tests.py`,
  `comptes/tests.py` — 90 tests : la chaîne d'analyse, les pages, et le
  cloisonnement des données entre utilisateurs.
- `config/settings.py` — réglages du projet (SQLite, français, `AUTH_USER_MODEL`).

## Installer le projet sur une nouvelle machine

```bash
git clone https://github.com/Aicha-Dembele/green-dev-africa.git
cd green-dev-africa
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

**Puis crée ta clé secrète.** Elle n'est volontairement pas dans le dépôt :
une clé secrète publiée permettrait de fabriquer de fausses sessions.
Recopie le modèle, génère une clé, et colle-la dedans à la place de
`colle-ici-ta-cle-secrete` :

```bash
copy config\local_settings.example.py config\local_settings.py
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

**Enfin, prépare la base et lance le serveur :**

```bash
python manage.py migrate
python manage.py charger_referentiel
python manage.py createsuperuser
python manage.py runserver
```

Puis <http://127.0.0.1:8000/> pour l'application, et
<http://127.0.0.1:8000/admin/> pour l'administration.

La base de données n'est pas partagée non plus — elle contient des comptes
et des mots de passe, chacun a la sienne. Pour la remplir avec un projet de
démonstration et deux analyses déjà exécutées :
`python manage.py creer_jeu_de_demo`.

## Relancer le projet les jours suivants

```bash
venv\Scripts\activate
python manage.py runserver
```

## Les pages du site

| Adresse | Page | Cas d'utilisation |
|---|---|---|
| `/` | Tableau de bord | Consulter le tableau de bord |
| `/comptes/inscription/` | Créer un compte | Créer un compte |
| `/comptes/connexion/` | Se connecter | Se connecter |
| `/projets/nouveau/` | Nouveau projet | Créer un projet |
| `/projets/<id>/` | Fiche projet : historique + objectifs | — |
| `/projets/<id>/analyser/` | Lancer une analyse | Lancer une analyse, choisir le profil réseau et l'appareil |
| `/analyses/<id>/` | Résultat : score, problèmes, recommandations | Consulter les problèmes |
| `/analyses/<id>/rapport/` | Rapport + création de liens publics | Générer un rapport, Partager le rapport |
| `/analyses/<id>/rapport.json` | Export JSON | `exporterJSON()` du diagramme |
| `/r/<jeton>/` | **Page publique** d'un rapport partagé (sans compte) | Partager le rapport |
| `/projets/<id>/comparer/` | Comparer deux analyses | Comparer deux analyses (avant / après) |
| `/comptes/notifications/` | La cloche | Notifier l'utilisateur |
| `/regles/` | Seuils des règles — **administrateur seulement** | Régler les seuils |

Deux règles tenues partout dans les vues :

1. **Cloisonnement** : on ne charge jamais un objet par son seul numéro, on
   remonte toujours jusqu'au propriétaire (`projet__utilisateur=request.user`).
   Changer le numéro dans l'adresse donne une 404, pas les données d'autrui.
2. **Les écritures passent par POST**, avec jeton CSRF. Un lien cliqué ne
   modifie jamais la base.

Le style tient dans un seul fichier, `static/css/greendev.css` (charte bleu
nuit et turquoise), sans Bootstrap et sans police distante. Le seul
JavaScript du site est `static/js/greendev.js`, environ 1 Ko : il ajoute le
bouton « afficher le mot de passe », et les pages restent utilisables s'il ne
charge pas. Une application qui mesure la sobriété numérique ne peut pas
charger 300 Ko de cadre pour afficher un tableau.

Les règles de mot de passe sont volontairement réduites à deux (8 caractères
minimum, pas uniquement des chiffres) : voir le commentaire dans
`config/settings.py` pour remettre les deux autres avant la mise en ligne.

## Lancer les tests

```bash
python manage.py test
```

## Comment une analyse se déroule

1. L'utilisateur crée un **Projet** (nom + URL).
2. `projet.lancer_analyse(configuration=..., contexte=...)` crée une **Analyse**
   « en attente », avec sa **ConfigurationAnalyse** et son **UtilisateurContexte**.
3. **La mesure.** Si aucune valeur n'a été saisie à la main,
   `collecter_mesures()` appelle l'outil d'audit : il télécharge la page, y
   repère les images, scripts, feuilles de style et polices, les télécharge
   six à la fois comme un navigateur, et enregistre les **Indicateur** et les
   **RessourceWeb**. En audit « site complet », il suit en plus les liens
   internes et recommence sur chaque page.
4. `analyse.executer_analyse()` enchaîne :
   - `detecter_problemes()` compare chaque indicateur aux **RegleAnalyse**
     actives et crée un **ProblemeDetecte** + sa **Recommandation** ;
   - `calculer_score()` part de 100 et retire des points selon la gravité ;
   - `Rapport.construire_depuis()` fige les chiffres du **Rapport** ;
   - une **Notification** part vers le propriétaire du projet.
5. Le rapport s'exporte (`exporter_json()`) et se partage par lien temporaire
   (**PartageRapport**).
6. Deux analyses se comparent avec **ComparaisonAnalyse** (avant / après).

### Conventions

- Le `code` d'une **RegleAnalyse** porte le même nom que l'**Indicateur**
  qu'elle surveille (`poids_total`, `nombre_requetes`, `temps_chargement`,
  `donnees_transferees`, `poids_images`, `poids_javascript`, `poids_css`,
  `elements_dom`, `images_non_optimisees`, `images_sans_alternative`).
- **Un seuil à 0 désigne une règle de comptage** : toute occurrence est déjà
  un défaut (`images_sans_alternative`). La gravité se juge alors sur le
  nombre de cas (3 → moyenne, 10 → élevée, 20 → critique) et non sur un
  rapport de dépassement, qui n'aurait aucun sens. Les deux barèmes sont dans
  `ProblemeDetecte.PALIERS_DEPASSEMENT` et `PALIERS_COMPTAGE`.
- Les noms du diagramme sont en `camelCase`, ceux du code en `snake_case`,
  comme le veut Django : `dateAnalyse` → `date_analyse`,
  `executerAnalyse()` → `executer_analyse()`.
- Une composition du diagramme (le losange) devient
  `on_delete=models.CASCADE` ; une simple association vers une table de
  paramétrage devient `on_delete=models.PROTECT`.

## Les deux types d'audit

La **ConfigurationAnalyse** choisie au lancement commande réellement le
travail de l'outil :

| Réglage | Effet |
|---|---|
| **Une seule page** | mesure l'adresse donnée, rien d'autre |
| **Site complet** | part de cette adresse, suit les liens internes, mesure plusieurs pages et renvoie les **moyennes par page** |
| **Rapide** | plafonds : 5 pages, 30 fichiers par page |
| **Approfondi** | plafonds : 15 pages, 60 fichiers par page |

Pourquoi des moyennes et non des totaux : les seuils des règles sont pensés
pour une page (« moins de 500 Ko »). Un total sur dix pages les ferait
exploser sans rien dire d'utile. L'indicateur `nombre_pages` indique sur
combien de pages la moyenne a été faite.

En parcourant un site, l'outil :

- ne sort jamais du domaine de départ ;
- ignore les liens qui ne sont pas des pages (PDF, images, archives) ;
- **respecte le fichier `robots.txt`** du site, qui dit aux robots où ils
  n'ont pas à aller ;
- compare les adresses **d'arrivée** après redirection, pour ne pas mesurer
  deux fois la même page sous deux adresses ;
- dédoublonne les fichiers : une feuille de style servie par les dix pages
  n'apparaît qu'une fois.

## Ce que l'outil d'audit ne voit pas

Il mesure la page telle qu'elle arrive du serveur. Les fichiers ajoutés
ensuite par JavaScript lui échappent — c'est à dire et à assumer devant le
jury : ce qu'il mesure correspond à ce que le visiteur paie avant même que la
page ne s'anime. Il plafonne aussi le nombre de pages et de fichiers (voir le tableau
ci-dessus) et abandonne une requête au bout de 10 secondes, pour ne pas
s'acharner sur un site lent.

Il refuse les adresses internes (`localhost`, `192.168.x.x`…) : sans ce
contrôle, on pourrait faire visiter son propre réseau au serveur et s'en
faire recopier le contenu (faille SSRF).

## Ce qui reste à faire

- [ ] `Rapport.generer_pdf()`, à écrire avec le gabarit du rapport.
- [ ] L'envoi des notifications par e-mail (acteur « Service d'e-mail »).
