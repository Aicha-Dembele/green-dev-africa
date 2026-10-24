"""L'outil d'audit web : va chercher la page et la pèse.

C'est l'acteur « Outil d'audit web » du diagramme des cas d'utilisation.
Il ne connaît ni Django ni la base : on lui donne une adresse, il renvoie des
mesures et la liste des fichiers téléchargés. C'est `Analyse.collecter_mesures()`
qui fait le pont avec les modèles.

Comment il travaille :

1. il télécharge la page HTML ;
2. il la lit pour y trouver les images, scripts, feuilles de style, polices
   et vidéos qu'un navigateur devrait aller chercher ;
3. il télécharge ces fichiers (six à la fois, comme un navigateur) pour
   connaître leur poids réel ;
4. il en tire les indicateurs du catalogue.

Ce qu'il ne voit pas, et qu'il faut savoir dire au jury : les fichiers
ajoutés par JavaScript après l'affichage. Il mesure la page telle qu'elle
arrive du serveur, ce qui correspond exactement à ce que paie un visiteur
sur un forfait limité avant même que la page ne s'anime.
"""

import ipaddress
import socket
import time
import urllib.robotparser
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from urllib.parse import urldefrag, urljoin, urlparse

import requests

from .indicateurs import categorie_de, unite_de

#: On s'annonce honnêtement auprès des serveurs qu'on interroge.
AGENT = "GreenDevAfrica/1.0 (outil d'audit de sobriete numerique)"

DELAI_SECONDES = 10        # au-delà, on abandonne une requête
MAX_RESSOURCES = 60        # on ne télécharge pas un site entier
MAX_PAGES = 10             # plafond de pages en audit « site complet »
MAX_OCTETS_PAR_FICHIER = 5 * 1024 * 1024   # 5 Mo : on ne tire pas tout d'une vidéo
CONNEXIONS_PARALLELES = 6  # ce qu'ouvre un navigateur sur un même domaine

#: Adresses qu'on ne suit pas en parcourant le site : ce ne sont pas des pages.
EXTENSIONS_NON_HTML = (
    ".pdf", ".zip", ".rar", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".avif", ".ico",
    ".mp3", ".mp4", ".webm", ".avi", ".css", ".js", ".json", ".xml",
    ".woff", ".woff2", ".ttf", ".otf",
)

#: Au-dessus de cette taille, une image est jugée non optimisée.
SEUIL_IMAGE_KO = 150
#: Ces formats sont déjà compressés correctement.
FORMATS_MODERNES = (".webp", ".avif", ".svg")


class ErreurCollecte(Exception):
    """Le site n'a pas pu être mesuré. Le message est destiné à l'utilisateur."""


# ---------------------------------------------------------------------------
#  Lecture du HTML
# ---------------------------------------------------------------------------


class _LecteurHTML(HTMLParser):
    """Repère les fichiers que la page demande, et compte ses balises."""

    TYPES_PAR_EXTENSION = {
        ".css": "style",
        ".js": "script",
        ".woff": "police",
        ".woff2": "police",
        ".ttf": "police",
        ".otf": "police",
        ".mp4": "video",
        ".webm": "video",
    }
    EXTENSIONS_IMAGE = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif", ".svg", ".ico")

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.nb_balises = 0
        self.images_sans_alternative = 0
        self.trouvailles = []  # [(adresse brute, type)]
        self.liens = []        # les href des <a>, pour parcourir le site

    def handle_starttag(self, balise, attributs):
        self.nb_balises += 1
        attrs = dict(attributs)

        if balise == "a":
            adresse = (attrs.get("href") or "").strip()
            if adresse and not adresse.startswith(
                ("data:", "javascript:", "#", "mailto:", "tel:")
            ):
                self.liens.append(adresse)

        elif balise == "img":
            # Un alt vide est un choix légitime pour une image décorative :
            # on ne compte que les images où l'attribut manque complètement.
            if "alt" not in attrs:
                self.images_sans_alternative += 1
            self._ajouter(attrs.get("src"), "image")

        elif balise == "script":
            self._ajouter(attrs.get("src"), "script")

        elif balise == "link":
            relations = (attrs.get("rel") or "").lower().split()
            adresse = attrs.get("href")
            if "stylesheet" in relations:
                self._ajouter(adresse, "style")
            elif "preload" in relations and attrs.get("as") == "font":
                self._ajouter(adresse, "police")
            elif "icon" in relations:
                self._ajouter(adresse, "image")

        elif balise in ("source", "video", "audio", "embed"):
            self._ajouter(attrs.get("src"), None)

    def _ajouter(self, adresse, type_force):
        if not adresse:
            return
        adresse = adresse.strip()
        # Une image écrite directement dans le HTML (data:) ne coûte pas de
        # requête supplémentaire : on la laisse de côté.
        if not adresse or adresse.startswith(("data:", "javascript:", "#", "mailto:")):
            return
        self.trouvailles.append((adresse, type_force or self._deviner(adresse)))

    @classmethod
    def _deviner(cls, adresse):
        chemin = urlparse(adresse).path.lower()
        for extension, type_fichier in cls.TYPES_PAR_EXTENSION.items():
            if chemin.endswith(extension):
                return type_fichier
        if chemin.endswith(cls.EXTENSIONS_IMAGE):
            return "image"
        return "autre"


# ---------------------------------------------------------------------------
#  Garde-fou : on ne laisse pas le serveur visiter son propre réseau
# ---------------------------------------------------------------------------


def verifier_adresse(url):
    """Refuse ce qui n'est pas un vrai site public.

    Sans ce contrôle, quelqu'un pourrait faire analyser `http://localhost/...`
    ou une adresse interne : le serveur irait la chercher pour lui et en
    recopierait le contenu. C'est la faille appelée SSRF.
    """
    decoupe = urlparse(url)
    if decoupe.scheme not in ("http", "https"):
        raise ErreurCollecte("Seules les adresses http:// et https:// sont analysables.")
    if not decoupe.hostname:
        raise ErreurCollecte("Cette adresse ne contient pas de nom de domaine.")

    try:
        adresses = socket.getaddrinfo(decoupe.hostname, None)
    except socket.gaierror:
        raise ErreurCollecte(
            f"Le domaine « {decoupe.hostname} » est introuvable. Vérifie l'adresse."
        )

    for information in adresses:
        adresse_ip = ipaddress.ip_address(information[4][0])
        if (
            adresse_ip.is_private
            or adresse_ip.is_loopback
            or adresse_ip.is_link_local
            or adresse_ip.is_reserved
        ):
            raise ErreurCollecte(
                "Cette adresse pointe vers un réseau interne : analyse refusée."
            )


# ---------------------------------------------------------------------------
#  La collecte
# ---------------------------------------------------------------------------


def _telecharger(session, url):
    """Renvoie (octets, type MIME) ou None si le fichier n'a pas pu être lu."""
    try:
        with session.get(url, timeout=DELAI_SECONDES, stream=True) as reponse:
            reponse.raise_for_status()
            total = 0
            for morceau in reponse.iter_content(chunk_size=16384):
                total += len(morceau)
                if total >= MAX_OCTETS_PAR_FICHIER:
                    break
            return total, reponse.headers.get("Content-Type", "")
    except requests.RequestException:
        # Un fichier manquant ou trop lent ne doit pas faire échouer l'audit :
        # on le signale en l'ignorant, comme le ferait un navigateur.
        return None


def collecter(
    url,
    inclure_medias=True,
    inclure_javascript=True,
    session=None,
    max_ressources=MAX_RESSOURCES,
):
    """Mesure une page. Renvoie {mesures, ressources, liens, url_finale}.

    `liens` contient les adresses des autres pages du même site : c'est ce
    qui permet à `collecter_site()` de parcourir le site.

    `session` permet de passer un objet de remplacement dans les tests, pour
    ne pas sortir sur le réseau.
    """
    verifier_adresse(url)

    fermer = session is None
    if session is None:
        session = requests.Session()
        session.headers.update({"User-Agent": AGENT, "Accept-Encoding": "gzip, deflate"})

    try:
        depart = time.monotonic()

        # 1. la page elle-même
        try:
            reponse = session.get(url, timeout=DELAI_SECONDES)
            reponse.raise_for_status()
        except requests.Timeout:
            raise ErreurCollecte(
                f"Le site n'a pas répondu en moins de {DELAI_SECONDES} secondes."
            )
        except requests.RequestException as erreur:
            raise ErreurCollecte(f"Impossible d'ouvrir cette page : {erreur}")

        html = reponse.text
        octets_html = len(reponse.content)
        adresse_finale = reponse.url  # après d'éventuelles redirections

        # 2. ce que la page réclame
        lecteur = _LecteurHTML()
        lecteur.feed(html)

        types_ignores = set()
        if not inclure_medias:
            types_ignores |= {"image", "video"}
        if not inclure_javascript:
            types_ignores.add("script")

        a_telecharger, deja_vues = [], set()
        for adresse_brute, type_fichier in lecteur.trouvailles:
            if type_fichier in types_ignores:
                continue
            adresse = urljoin(adresse_finale, adresse_brute)
            if not adresse.startswith(("http://", "https://")) or adresse in deja_vues:
                continue
            deja_vues.add(adresse)
            a_telecharger.append((adresse, type_fichier))
            if len(a_telecharger) >= max_ressources:
                break

        # 3. on les télécharge comme le ferait un navigateur
        ressources = []
        if a_telecharger:
            with ThreadPoolExecutor(max_workers=CONNEXIONS_PARALLELES) as pool:
                resultats = pool.map(
                    lambda cible: _telecharger(session, cible[0]), a_telecharger
                )
                for (adresse, type_fichier), resultat in zip(a_telecharger, resultats):
                    if resultat is None:
                        continue
                    octets, _mime = resultat
                    taille_ko = round(octets / 1024, 2)
                    ressources.append(
                        {
                            "url": adresse,
                            "type": type_fichier,
                            "taille": taille_ko,
                            "optimisable": _est_optimisable(
                                adresse, type_fichier, taille_ko
                            ),
                        }
                    )

        duree = time.monotonic() - depart

        # 4. on en tire les indicateurs
        poids_ko = round((octets_html + sum(r["taille"] * 1024 for r in ressources)) / 1024, 2)
        mesures = {
            "poids_total": poids_ko,
            "donnees_transferees": round(poids_ko / 1024, 3),
            "nombre_requetes": 1 + len(ressources),
            "temps_chargement": round(duree, 2),
            "poids_images": _somme(ressources, "image"),
            "poids_javascript": _somme(ressources, "script"),
            "poids_css": _somme(ressources, "style"),
            "elements_dom": lecteur.nb_balises,
            "images_non_optimisees": sum(
                1 for r in ressources if r["type"] == "image" and r["optimisable"]
            ),
            "images_sans_alternative": lecteur.images_sans_alternative,
            "nombre_pages": 1,
        }

        return {
            "mesures": mesures,
            "ressources": ressources,
            "liens": _liens_internes(lecteur.liens, adresse_finale),
            "url_finale": adresse_finale,
        }

    finally:
        if fermer:
            session.close()


def _liens_internes(liens_bruts, adresse_page):
    """Garde les liens qui mènent à une autre page du même site.

    On écarte : les autres domaines, les fichiers qui ne sont pas des pages
    (PDF, images…) et les ancres `#section`, qui ramènent à la même page.
    """
    hote = urlparse(adresse_page).netloc
    retenus, deja_vus = [], set()

    for brut in liens_bruts:
        adresse, _ancre = urldefrag(urljoin(adresse_page, brut))
        decoupe = urlparse(adresse)
        if decoupe.scheme not in ("http", "https") or decoupe.netloc != hote:
            continue
        if decoupe.path.lower().endswith(EXTENSIONS_NON_HTML):
            continue
        if adresse in deja_vus or adresse == adresse_page:
            continue
        deja_vus.add(adresse)
        retenus.append(adresse)

    return retenus


def _lire_robots(session, url):
    """Charge le robots.txt du site. Renvoie None s'il n'y en a pas.

    Ce fichier est la façon dont un site dit aux robots où ils n'ont pas à
    aller. On le respecte : parcourir plusieurs pages d'un site qui ne nous
    appartient pas demande d'être poli.
    """
    decoupe = urlparse(url)
    adresse = f"{decoupe.scheme}://{decoupe.netloc}/robots.txt"
    try:
        reponse = session.get(adresse, timeout=DELAI_SECONDES)
        if reponse.status_code != 200:
            return None
        lecteur = urllib.robotparser.RobotFileParser()
        lecteur.parse(reponse.text.splitlines())
        return lecteur
    except (requests.RequestException, UnicodeDecodeError):
        return None


def collecter_site(
    url,
    max_pages=MAX_PAGES,
    inclure_medias=True,
    inclure_javascript=True,
    session=None,
    max_ressources=MAX_RESSOURCES,
):
    """Audit « site complet » : mesure plusieurs pages et en fait la moyenne.

    On part de l'adresse donnée, on suit ses liens internes, et on recommence
    jusqu'à `max_pages` pages. Les indicateurs renvoyés sont les **moyennes
    par page** : c'est ce qui garde un sens face aux seuils, qui sont pensés
    pour une page (« moins de 500 Ko »). S'y ajoute `nombre_pages`, qui dit
    sur combien de pages la moyenne a été faite.

    Les fichiers sont dédoublonnés : une feuille de style chargée par les dix
    pages n'est comptée qu'une fois dans la liste des ressources.
    """
    verifier_adresse(url)

    fermer = session is None
    if session is None:
        session = requests.Session()
        session.headers.update({"User-Agent": AGENT, "Accept-Encoding": "gzip, deflate"})

    try:
        robots = _lire_robots(session, url)

        a_visiter = [url]
        deja_vues = set()   # adresses déjà demandées
        mesurees = set()    # adresses d'arrivée déjà comptées
        resultats = []
        ressources = {}

        while a_visiter and len(resultats) < max_pages:
            page = a_visiter.pop(0)
            if page in deja_vues:
                continue
            deja_vues.add(page)

            if robots is not None and not robots.can_fetch(AGENT, page):
                continue

            try:
                resultat = collecter(
                    page,
                    inclure_medias=inclure_medias,
                    inclure_javascript=inclure_javascript,
                    session=session,
                    max_ressources=max_ressources,
                )
            except ErreurCollecte:
                # La page d'entrée doit répondre ; pour les suivantes, une
                # page cassée ne doit pas faire échouer tout l'audit.
                if not resultats:
                    raise
                continue

            # C'est l'adresse d'ARRIVÉE qui dit quelle page on a vraiment
            # mesurée : plusieurs adresses peuvent mener à la même
            # (surveylama.com, surveylama.com/ et surveylama.com/en
            # aboutissent toutes les trois à la page d'accueil). Sans ce
            # contrôle, l'accueil pesait deux fois dans la moyenne.
            finale = resultat["url_finale"]
            if finale in mesurees:
                continue
            mesurees.add(finale)
            deja_vues.add(finale)

            resultats.append(resultat)
            for ressource in resultat["ressources"]:
                ressources.setdefault(ressource["url"], ressource)
            for lien in resultat["liens"]:
                if lien not in deja_vues and lien not in a_visiter:
                    a_visiter.append(lien)

        if not resultats:
            raise ErreurCollecte(
                "Aucune page n'a pu être analysée : le site est vide ou interdit "
                "par robots.txt."
            )

        mesures = {
            cle: _moyenne(resultats, cle) for cle in resultats[0]["mesures"]
        }
        mesures["nombre_pages"] = len(resultats)

        return {
            "mesures": mesures,
            "ressources": list(ressources.values()),
            "liens": [],
            "url_finale": resultats[0]["url_finale"],
            "pages": [resultat["url_finale"] for resultat in resultats],
        }

    finally:
        if fermer:
            session.close()


def _moyenne(resultats, cle):
    valeurs = [resultat["mesures"][cle] for resultat in resultats]
    return round(sum(valeurs) / len(valeurs), 2)


def _somme(ressources, type_fichier):
    return round(
        sum(r["taille"] for r in ressources if r["type"] == type_fichier), 2
    )


def _est_optimisable(adresse, type_fichier, taille_ko):
    """Une image lourde dans un format ancien peut presque toujours être allégée."""
    if type_fichier != "image":
        return False
    chemin = urlparse(adresse).path.lower()
    if chemin.endswith(FORMATS_MODERNES):
        return False
    return taille_ko > SEUIL_IMAGE_KO


def unites_et_categories(mesures):
    """Prépare les mesures pour la création des Indicateur en base."""
    return [
        {
            "nom": code,
            "valeur": valeur,
            "unite": unite_de(code),
            "categorie": categorie_de(code),
        }
        for code, valeur in mesures.items()
    ]
