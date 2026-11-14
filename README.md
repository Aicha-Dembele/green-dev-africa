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
- `analyses/pdf.py` — **la fabrique du PDF** : reçoit un rapport, rend des
  octets. Comme le collecteur, elle ne touche jamais à la base.
- `analyses/indicateurs.py` — le catalogue des indicateurs (intitulé, unité,
  catégorie), source unique lue par le formulaire, le collecteur et la démo.
- `analyses/management/commands/charger_referentiel.py` — les règles d'analyse
  et les conseils d'optimisation (le paramétrage du moteur).
- `analyses/tests.py` (moteur), `analyses/tests_vues.py`, `projets/tests.py`,
  `comptes/tests.py` — 90 tests : la chaîne d'analyse, les pages, et le
  cloisonnement des données entre utilisateurs.
- `config/settings.py` — réglages du projet (PostgreSQL en production, SQLite
  en local, français, `AUTH_USER_MODEL`).

## Installer le projet sur une nouvelle machine

```bash
git clone https://github.com/Aicha-Dembele/green-dev-africa.git
cd green-dev-africa
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

**Configure ensuite les variables d'environnement.** Le fichier
[`.env.example`](./.env.example) est un modèle à recopier dans ton outil
d'hébergement ou ton terminal ; Django ne charge pas automatiquement un
fichier `.env`. Ne publie jamais la vraie `DJANGO_SECRET_KEY` : elle permet
notamment de signer les sessions.

Pour le déploiement Systalink, configure au minimum `DJANGO_DEBUG=False`,
une `DJANGO_SECRET_KEY` générée aléatoirement, et
`DJANGO_ALLOWED_HOSTS=green-dev-africa-92575681.platform-systalink.com`.
En production, configure `DATABASE_URL` avec l'URL de la base PostgreSQL
persistante fournie par Systalink. L'application refuse volontairement de
démarrer hors du mode debug si cette variable est absente, afin d'éviter de
perdre les comptes, projets et analyses dans un fichier SQLite du conteneur.
En local, sans `DATABASE_URL`, SQLite reste utilisé automatiquement.
Si Systalink termine HTTPS devant un proxy qui transmet et remplace
`X-Forwarded-Proto`, configure `DJANGO_BEHIND_PROXY=True` pour éviter une
boucle de redirection HTTPS.

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Pour le développement local sous PowerShell, active explicitement le mode
debug avant de lancer le serveur :

```powershell
$env:DJANGO_DEBUG = "True"
```

Hors mode debug, l'application exige `DJANGO_SECRET_KEY` et ne démarre pas
avec une clé de secours. En production, configure aussi `DJANGO_DEBUG=False`
et `DJANGO_ALLOWED_HOSTS` avec les noms d'hôte exacts du site. HTTPS et les
cookies sécurisés sont imposés automatiquement hors mode debug. Ne règle
`DJANGO_BEHIND_PROXY=True` qu'après avoir vérifié que le proxy de confiance
remplace lui-même l'en-tête `X-Forwarded-Proto`.

### Déploiement avec Docker

Le `Dockerfile` du dépôt définit le délai d'attente de pip à 120 secondes et
jusqu'à 10 tentatives pour les téléchargements de dépendances, afin de mieux
résister aux connexions lentes ou interrompues. Au démarrage, il applique les
migrations, charge le référentiel d'analyse, collecte les fichiers statiques,
puis démarre Gunicorn. Configure dans l'environnement du service les variables
de production décrites dans `.env.example`, ainsi que `PORT` si la plateforme
ne le fournit pas automatiquement.

### Variables Systalink

Configure dans l'environnement du service :

```text
DJANGO_DEBUG=False
DJANGO_SECRET_KEY=<clé aléatoire générée>
DJANGO_ALLOWED_HOSTS=green-dev-africa-92575681.platform-systalink.com
DJANGO_BEHIND_PROXY=True
DATABASE_URL=postgresql://<utilisateur>:<mot-de-passe>@<hôte>:5432/<base>
```

Ne mets jamais la vraie clé secrète ou le mot de passe PostgreSQL dans Git.
`DATABASE_URL` est prioritaire sur SQLite ; `SQLITE_PATH` ne sert qu'au
développement local.

La base est préparée par [`gunicorn.conf.py`](./gunicorn.conf.py), que
gunicorn lit **automatiquement** depuis la racine du projet, quelle que soit
la commande qui le lance (Systalink lance gunicorn lui-même et ignore la
commande du `Dockerfile`). Avant de créer ses workers, gunicorn :

1. affiche la base utilisée (moteur, hôte, port, nom — jamais le mot de passe) ;
2. applique les migrations, puis vérifie qu'aucune ne reste en attente ;
3. charge le référentiel d'analyse.

Si une étape échoue, gunicorn ne démarre pas et l'erreur est dans les logs.
Au démarrage, les logs doivent montrer les lignes `[demarrage] …`. Le même
fichier règle le délai (180 s, une analyse peut être longue) et les threads ;
voir `GUNICORN_WORKERS`, `GUNICORN_THREADS`, `GUNICORN_TIMEOUT`.

**Enfin, prépare la base et lance le serveur :**

```bash
python manage.py migrate
python manage.py charger_referentiel
python manage.py createsuperuser
python manage.py runserver
```

Sur une plateforme qui n'utilise pas le `Dockerfile`, exécute avant de démarrer
Gunicorn les commandes `python manage.py migrate --noinput`,
`python manage.py charger_referentiel` et
`python manage.py collectstatic --noinput`.

Dans un second terminal, démarre aussi le service qui traite les analyses :

```bash
python manage.py traiter_analyses
```

Les demandes sont conservées dans la base partagée entre le site et ce
processus : elles passent de « En attente » à « En cours », puis « Terminée »
ou « Échouée ». La page de suivi actualise le statut automatiquement. En
production, configure `traiter_analyses` comme un processus de travail
persistant, lancé avec la même configuration et la même base que le serveur
Django. Sans ce processus, les demandes restent en attente. La file repose sur
la base existante et ne nécessite pas Redis.

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

Dans un second terminal, relance aussi le traitement des analyses :

```bash
python manage.py traiter_analyses
```

## Envoyer de vrais e-mails (mot de passe oublié, notifications)

Par défaut, aucun e-mail ne part : Django les affiche dans le terminal du
serveur. C'est pratique pour tester : le lien « mot de passe oublié » s'y
lit directement. `config/local_settings.py` n'est chargé qu'en mode
développement ; les réglages de production doivent être configurés via les
variables d'environnement de l'hébergeur.

Pour les envoyer vraiment avec Gmail, crée `config/local_settings.py`. Ce
fichier est ignoré par git et ne doit jamais être publié. Il est chargé en
dernier et remplace les réglages de `settings.py` :

```python
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = "ton.adresse@gmail.com"
EMAIL_HOST_PASSWORD = "..."  # mot de passe d'APPLICATION Gmail, pas le mot de passe du compte
DEFAULT_FROM_EMAIL = "Green Dev Africa <ton.adresse@gmail.com>"
```

Le mot de passe d'application se crée sur
<https://myaccount.google.com/apppasswords>, avec la validation en deux
étapes activée. Sur un hébergeur, mets plutôt ces valeurs dans les variables
`DJANGO_EMAIL_*` de [`.env.example`](./.env.example).

## Les pages du site

| Adresse | Page | Cas d'utilisation |
|---|---|---|
| `/` | Présentation (visiteurs) / tableau de bord (membres connectés) | Découvrir Green Dev Africa / Consulter le tableau de bord |
| `/comptes/inscription/` | Créer un compte | Créer un compte |
| `/comptes/connexion/` | Se connecter | Se connecter |
| `/comptes/mot-de-passe-oublie/` | Mot de passe oublié : on tape son adresse e-mail, le lien reçu ouvre `/comptes/nouveau-mot-de-passe/…` (valable 24 h, une seule fois) | Réinitialiser son mot de passe |
| `/projets/nouveau/` | Nouveau projet | Créer un projet |
| `/projets/<id>/` | Fiche projet : historique + objectifs | — |
| `/projets/<id>/analyser/` | Lancer une analyse | Lancer une analyse, choisir le profil réseau et l'appareil |
| `/analyses/<id>/` | Résultat : score, problèmes, recommandations | Consulter les problèmes |
| `/analyses/<id>/rapport/` | Rapport + création de liens publics | Générer un rapport, Partager le rapport |
| `/analyses/<id>/rapport.json` | Export JSON | `exporterJSON()` du diagramme |
| `/analyses/<id>/rapport.pdf` | Export PDF | `genererPDF()` du diagramme |
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
JavaScript du site est `static/js/greendev.js`, de quelques Ko : il améliore
le suivi d'une analyse et ajoute le bouton « afficher le mot de passe » ; les
pages restent utilisables s'il ne charge pas. Une application qui mesure la
sobriété numérique ne peut pas charger 300 Ko de cadre pour afficher un tableau.

Les règles de mot de passe sont volontairement réduites à deux (8 caractères
minimum, pas uniquement des chiffres) : voir le commentaire dans
`config/settings.py` pour remettre les deux autres avant la mise en ligne.

## Tarifs

Le prix est de 50 FCFA par crédit. Le montant libre doit être au moins de 1 000 FCFA et avancer par pas de 500 FCFA, jusqu'à 50 000 FCFA. Le nombre de crédits est calculé par `montant FCFA / PRIX_CREDIT_FCFA`.

Les valeurs sont centralisées dans `credits/config.py` : `PRIX_CREDIT_FCFA`, `ACHAT_MINIMUM_FCFA`, `ACHAT_PAS_FCFA`, `ACHAT_MAXIMUM_FCFA`, `MONTANTS_SUGGERES` et `TEXTE_OBTENIR_CREDITS`. Les coûts des analyses, les crédits de bienvenue et le quota gratuit y sont également définis. La page `Tarifs` et son calculateur utilisent ces valeurs.

Le parcours d'achat utilise actuellement une simulation gratuite : après vérification du montant, l'utilisateur peut confirmer et recevoir les crédits sans débit d'argent. Ce comportement est explicitement signalé dans l'interface et le journal des crédits. Aucun prestataire de paiement réel n'est intégré. Il n'y a pas de bonus de volume ni d'expiration des crédits.

## Lancer les tests

```bash
python manage.py test
python manage.py check
```

## Système de crédits

Le système de crédits est un journal comptable par utilisateur. Chaque utilisateur a un `SoldeCredits` et une liste de `JournalCredits` ; le solde de référence est toujours recalculé à partir de la somme des montants du journal.

- `credits.services.ajouter_credits()` ajoute un montant au journal et recalcule le solde.
- `credits.services.debiter_pour_analyse()` retire le coût d'une analyse quand les fonds sont suffisants.
- `credits.services.rembourser_analyse()` crédite le client si l'analyse échoue et qu'un débit a bien été enregistré.
- `credits.services.attribuer_credits_bienvenue()` n'attribue les crédits de bienvenue qu'une seule fois par utilisateur.
- Les crédits ne sont jamais expiés : le solde reste valide tant qu'il n'est pas dépensé ou ajusté par l'administration.
- Le quota gratuit est calculé par mois calendaire (`date_analyse__year`, `date_analyse__month`) ; il se réinitialise au 1er jour du mois. Il ne s'agit pas d'un quota glissant sur 30 jours.
- Les coûts sont configurés dans `credits/config.py` : `COUT_PAGE_HORS_QUOTA`, `COUT_SITE_COMPLET_RAPIDE`, `COUT_SITE_COMPLET_APPROFONDI`, `QUOTA_GRATUIT_MENSUEL` et les constantes de type d'audit.
- L'interface utilisateur expose le solde, le quota gratuit restant et l'historique des mouvements.
- Les pages « Mes crédits » et « Tarifs » mènent au parcours d'achat, qui affiche un récapitulatif et permet de confirmer une simulation gratuite. Pour passer à un paiement réel, remplacer cette confirmation par l'intégration d'un prestataire et n'ajouter les crédits qu'après confirmation de son paiement.
- La page d'administration permet de voir le solde et les mouvements de chaque utilisateur et d'ajouter des crédits via une action dédiée, sans modifier directement le `solde` de la table.

Ce qui n'est pas encore implémenté : intégration d'un prestataire de paiement réel, confirmation d'e-mail avant attribution, et les mécanismes de rate limiting pour bloquer la création de comptes en série.

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

## L'export PDF

`Rapport.generer_pdf()` rend le rapport en octets PDF ; le dessin vit dans
`analyses/pdf.py` et s'appuie sur **ReportLab**. Pas de passage par le HTML :
les bibliothèques qui convertissent une page web en PDF réclament sous
Windows des composants système à installer à la main, ce qu'on ne pouvait
pas se permettre pour une démonstration.

Le PDF est **sur fond blanc**, volontairement : un fond bleu nuit couvrirait
la page d'encre à l'impression, ce qui serait difficile à défendre pour un
outil qui mesure la sobriété. La charte reste dans le bandeau et les accents,
et les seuils de couleur du score (70 et 40) sont les mêmes qu'à l'écran.

Un rapport de cinq problèmes tient en 8 Ko sur trois pages, exemples de code
compris. Les textes venus de la base y sont échappés avant d'être insérés :
ReportLab lit ses paragraphes comme du mini-HTML, et une adresse contenant
« & » ferait échouer la génération entière.

## La mention de méthode

Elle est affichée au pied de **chaque rapport**, y compris le rapport public
partagé — c'est celui qui part chez un client, donc celui où elle protège le
plus. Même texte que le PDF et que la page d'accueil : ce qui est mesuré, ce
qui ne l'est pas (les fichiers ajoutés par JavaScript), et le fait que les
résultats ne constituent pas un calcul d'empreinte carbone.

Un test de `projets/tests.py` vérifie que la mention existe toujours sur
l'accueil, et un autre sur le rapport. Ils vérifient la présence des mots
« empreinte carbone », pas la formulation exacte : une réécriture passe, une
suppression casse.

## La comparaison avant / après

La page `/comparaisons/<id>/` ne se contente pas des deux scores :

- **chaque indicateur** est repris avant / après, avec l'écart. Pour tous nos
  indicateurs, baisser est un progrès — c'est le propre d'un outil de
  sobriété. Seul `nombre_pages` est affiché sans jugement : passer de 1 à 5
  pages analysées n'est ni un progrès ni une régression.
- **le bilan des problèmes** en trois colonnes : résolus, toujours là,
  apparus. Deux problèmes sont « le même » quand ils viennent de la même
  règle : c'est la seule clé stable entre deux analyses, puisque les
  identifiants sont recréés à chaque exécution et que les intitulés
  contiennent la valeur mesurée.

Seul le **nombre** de problèmes résolus est figé en base, comme les scores,
pour la liste des comparaisons passées. Le détail est recalculé à
l'affichage : les indicateurs et les problèmes des deux analyses sont déjà
en base, en faire une seconde copie n'ajouterait qu'un risque de désaccord.

## Nommer le fichier en cause

Quand une règle vise un type de fichier (`poids_images`, `poids_javascript`,
`poids_css`, `images_non_optimisees`), le problème détecté porte le plus gros
fichier du lot : « c'est `banniere.png` » est actionnable, « vos images sont
trop lourdes » ne l'est pas. La recommandation cite alors ce fichier, et non
plus l'adresse de la page.

**On ne crée pas un problème par fichier**, délibérément : vingt images trop
lourdes donneraient vingt pénalités et un score écrasé pour une seule et même
erreur. On nomme le principal responsable, et la table des fichiers de la
page montre tous les autres, marqués « à alléger ».

`images_sans_alternative` est volontairement absente de cette liste : la plus
grosse image n'est pas forcément celle à qui il manque un texte alternatif,
et désigner un fichier au hasard serait pire que de n'en désigner aucun.

## Ce qui reste à faire

- [x] L'envoi des notifications par e-mail (acteur « Service d'e-mail ») via le backend Django configuré dans l'environnement.
