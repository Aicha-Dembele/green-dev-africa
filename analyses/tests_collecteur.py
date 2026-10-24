"""Tests de l'outil d'audit web.

Aucun de ces tests ne sort sur Internet : on remplace la session HTTP par un
faux site, dont on connaît à l'avance le contenu et le poids de chaque
fichier. C'est ce qui permet de vérifier des chiffres exacts.

Pour les lancer :  python manage.py test analyses.tests_collecteur
"""

from unittest.mock import patch

import requests
from django.contrib.auth import get_user_model
from django.test import TestCase

from analyses.collecteur import (
    ErreurCollecte,
    collecter,
    collecter_site,
    verifier_adresse,
)
from analyses.indicateurs import CATALOGUE
from analyses.management.commands.charger_referentiel import Command as Referentiel
from analyses.models import Analyse, Indicateur, RegleAnalyse, RessourceWeb
from projets.models import Projet

Utilisateur = get_user_model()


# ---------------------------------------------------------------------------
#  Un faux site, pour mesurer sans réseau
# ---------------------------------------------------------------------------


class FausseReponse:
    def __init__(self, contenu=b"", url="", echec=False):
        self.content = contenu
        self.url = url
        self.status_code = 200
        self.headers = {"Content-Type": "text/html"}
        self._echec = echec

    @property
    def text(self):
        return self.content.decode("utf-8")

    def raise_for_status(self):
        if self._echec:
            raise requests.HTTPError("404")

    def iter_content(self, chunk_size=8192):
        for debut in range(0, len(self.content), chunk_size):
            yield self.content[debut : debut + chunk_size]

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class FausseSession:
    """Répond d'après un annuaire {adresse: octets}. Tout le reste est en 404.

    `redirections` simule un serveur qui renvoie ailleurs : la réponse porte
    alors l'adresse d'arrivée, comme le fait requests.
    """

    def __init__(self, fichiers, redirections=None):
        self.fichiers = fichiers
        self.redirections = redirections or {}
        self.demandes = []

    def get(self, url, timeout=None, stream=False):
        self.demandes.append(url)
        cible = self.redirections.get(url, url)
        if cible not in self.fichiers:
            raise requests.ConnectionError(f"introuvable : {url}")
        return FausseReponse(self.fichiers[cible], url=cible)

    def close(self):
        pass


PAGE = """<html><head>
<link rel="stylesheet" href="/style.css">
<script src="/app.js"></script>
</head><body>
<img src="/logo.png" alt="Logo de la mairie">
<img src="/banniere.jpg">
<img src="data:image/gif;base64,R0lGOD" alt="">
<p>Bonjour</p>
</body></html>"""

OCTETS_PAGE = PAGE.encode("utf-8")

SITE = {
    "https://exemple.ml/": OCTETS_PAGE,
    "https://exemple.ml/style.css": b"x" * 2048,       # 2 Ko
    "https://exemple.ml/app.js": b"x" * 102400,        # 100 Ko
    "https://exemple.ml/logo.png": b"x" * 51200,       # 50 Ko
    "https://exemple.ml/banniere.jpg": b"x" * 204800,  # 200 Ko
}


class CollecteurTest(TestCase):
    """On mesure un site dont on connaît déjà toutes les réponses."""

    def setUp(self):
        # verifier_adresse interroge le DNS : on lui fait croire que le
        # domaine existe et pointe vers une adresse publique.
        correctif = patch(
            "analyses.collecteur.socket.getaddrinfo",
            return_value=[(2, 1, 6, "", ("93.184.216.34", 0))],
        )
        correctif.start()
        self.addCleanup(correctif.stop)

    def collecte(self, fichiers=None, **options):
        session = FausseSession(fichiers if fichiers is not None else SITE)
        resultat = collecter("https://exemple.ml/", session=session, **options)
        return resultat, session

    def test_les_quatre_chiffres_cles_sont_calcules(self):
        resultat, _ = self.collecte()
        mesures = resultat["mesures"]

        attendu_ko = round((len(OCTETS_PAGE) + (2 + 100 + 50 + 200) * 1024) / 1024, 2)
        self.assertEqual(mesures["poids_total"], attendu_ko)
        self.assertEqual(mesures["nombre_requetes"], 5)  # la page + 4 fichiers
        self.assertEqual(mesures["donnees_transferees"], round(attendu_ko / 1024, 3))
        self.assertGreaterEqual(mesures["temps_chargement"], 0)

    def test_le_poids_est_reparti_par_type_de_fichier(self):
        resultat, _ = self.collecte()
        mesures = resultat["mesures"]

        self.assertEqual(mesures["poids_images"], 250)
        self.assertEqual(mesures["poids_javascript"], 100)
        self.assertEqual(mesures["poids_css"], 2)

    def test_image_lourde_en_format_ancien_jugee_optimisable(self):
        resultat, _ = self.collecte()

        self.assertEqual(resultat["mesures"]["images_non_optimisees"], 1)
        banniere = next(
            r for r in resultat["ressources"] if r["url"].endswith("banniere.jpg")
        )
        logo = next(r for r in resultat["ressources"] if r["url"].endswith("logo.png"))
        self.assertTrue(banniere["optimisable"])
        self.assertFalse(logo["optimisable"])  # 50 Ko seulement

    def test_image_sans_attribut_alt_comptee(self):
        """alt="" est un choix valable pour une image décorative : non compté."""
        resultat, _ = self.collecte()

        self.assertEqual(resultat["mesures"]["images_sans_alternative"], 1)

    def test_elements_html_comptes(self):
        resultat, _ = self.collecte()

        # html, head, link, script, body, img, img, img, p
        self.assertEqual(resultat["mesures"]["elements_dom"], 9)

    def test_image_ecrite_dans_le_html_ne_compte_pas_comme_requete(self):
        _, session = self.collecte()

        self.assertFalse(any(url.startswith("data:") for url in session.demandes))

    def test_adresses_relatives_resolues(self):
        _, session = self.collecte()

        self.assertIn("https://exemple.ml/style.css", session.demandes)

    def test_fichier_manquant_ignore_sans_faire_echouer_laudit(self):
        site_troue = dict(SITE)
        del site_troue["https://exemple.ml/app.js"]

        resultat, _ = self.collecte(fichiers=site_troue)

        self.assertEqual(resultat["mesures"]["nombre_requetes"], 4)
        self.assertEqual(resultat["mesures"]["poids_javascript"], 0)

    def test_sans_les_medias_les_images_ne_sont_pas_telechargees(self):
        resultat, session = self.collecte(inclure_medias=False)

        self.assertEqual(resultat["mesures"]["poids_images"], 0)
        self.assertNotIn("https://exemple.ml/logo.png", session.demandes)

    def test_sans_le_javascript_les_scripts_ne_sont_pas_telecharges(self):
        resultat, session = self.collecte(inclure_javascript=False)

        self.assertEqual(resultat["mesures"]["poids_javascript"], 0)
        self.assertNotIn("https://exemple.ml/app.js", session.demandes)

    def test_page_injoignable_donne_un_message_clair(self):
        session = FausseSession({})

        with self.assertRaises(ErreurCollecte) as souleve:
            collecter("https://exemple.ml/", session=session)

        self.assertIn("Impossible d'ouvrir cette page", str(souleve.exception))


#  Un faux site de trois pages, pour l'audit « site complet »

PAGE_ACCUEIL = """<html><head><link rel="stylesheet" href="/style.css"></head><body>
<img src="/logo.png" alt="Logo">
<a href="/contact">Contact</a>
<a href="/services">Services</a>
<a href="https://autre-site.ml/page">Partenaire</a>
<a href="/brochure.pdf">Brochure</a>
<a href="#haut">Haut de page</a>
</body></html>"""

PAGE_CONTACT = """<html><head><link rel="stylesheet" href="/style.css"></head><body>
<p>Ecrivez-nous</p>
<a href="/">Accueil</a>
</body></html>"""

PAGE_SERVICES = """<html><head><link rel="stylesheet" href="/style.css">
<script src="/app.js"></script></head><body>
<h1>Nos services</h1>
</body></html>"""

PETIT_SITE = {
    "https://exemple.ml/": PAGE_ACCUEIL.encode("utf-8"),
    "https://exemple.ml/contact": PAGE_CONTACT.encode("utf-8"),
    "https://exemple.ml/services": PAGE_SERVICES.encode("utf-8"),
    "https://exemple.ml/style.css": b"x" * 2048,   # 2 Ko, partagé par les 3 pages
    "https://exemple.ml/logo.png": b"x" * 51200,   # 50 Ko, accueil seulement
    "https://exemple.ml/app.js": b"x" * 102400,    # 100 Ko, services seulement
}


class CollecteSiteTest(TestCase):
    """L'audit « site complet » : on suit les liens et on fait la moyenne."""

    def setUp(self):
        correctif = patch(
            "analyses.collecteur.socket.getaddrinfo",
            return_value=[(2, 1, 6, "", ("93.184.216.34", 0))],
        )
        correctif.start()
        self.addCleanup(correctif.stop)

    def parcourir(self, fichiers=None, **options):
        session = FausseSession(dict(fichiers if fichiers is not None else PETIT_SITE))
        resultat = collecter_site("https://exemple.ml/", session=session, **options)
        return resultat, session

    def test_les_trois_pages_sont_visitees(self):
        resultat, _ = self.parcourir()

        self.assertEqual(resultat["mesures"]["nombre_pages"], 3)
        self.assertEqual(
            sorted(resultat["pages"]),
            [
                "https://exemple.ml/",
                "https://exemple.ml/contact",
                "https://exemple.ml/services",
            ],
        )

    def test_les_mesures_sont_des_moyennes_par_page(self):
        resultat, _ = self.parcourir()
        mesures = resultat["mesures"]

        # requêtes : accueil 1+2, contact 1+1, services 1+2 → (3+2+3)/3
        self.assertEqual(mesures["nombre_requetes"], 2.67)
        # CSS : 2 Ko sur chacune des trois pages
        self.assertEqual(mesures["poids_css"], 2.0)
        # JavaScript : 100 Ko sur une seule page → 100/3
        self.assertEqual(mesures["poids_javascript"], 33.33)
        # images : 50 Ko sur une seule page → 50/3
        self.assertEqual(mesures["poids_images"], 16.67)
        # balises : 10 + 6 + 6 → 22/3
        self.assertEqual(mesures["elements_dom"], 7.33)

    def test_les_fichiers_partages_ne_sont_comptes_quune_fois(self):
        resultat, _ = self.parcourir()

        adresses = sorted(r["url"] for r in resultat["ressources"])
        self.assertEqual(
            adresses,
            [
                "https://exemple.ml/app.js",
                "https://exemple.ml/logo.png",
                "https://exemple.ml/style.css",
            ],
        )

    def test_le_plafond_de_pages_est_respecte(self):
        resultat, session = self.parcourir(max_pages=2)

        self.assertEqual(resultat["mesures"]["nombre_pages"], 2)
        self.assertNotIn("https://exemple.ml/services", session.demandes)

    def test_les_liens_vers_un_autre_site_ne_sont_pas_suivis(self):
        _, session = self.parcourir()

        self.assertFalse(any("autre-site.ml" in url for url in session.demandes))

    def test_les_liens_qui_ne_sont_pas_des_pages_ne_sont_pas_suivis(self):
        _, session = self.parcourir()

        self.assertNotIn("https://exemple.ml/brochure.pdf", session.demandes)

    def test_les_ancres_ne_relancent_pas_la_meme_page(self):
        resultat, _ = self.parcourir()

        self.assertEqual(resultat["mesures"]["nombre_pages"], 3)
        self.assertNotIn("https://exemple.ml/#haut", resultat["pages"])

    def test_le_robots_txt_est_respecte(self):
        site = dict(PETIT_SITE)
        site["https://exemple.ml/robots.txt"] = (
            b"User-agent: *\nDisallow: /services\n"
        )

        resultat, session = self.parcourir(fichiers=site)

        self.assertEqual(resultat["mesures"]["nombre_pages"], 2)
        self.assertNotIn("https://exemple.ml/services", session.demandes)

    def test_une_page_cassee_est_ignoree(self):
        site = dict(PETIT_SITE)
        del site["https://exemple.ml/services"]

        resultat, _ = self.parcourir(fichiers=site)

        self.assertEqual(resultat["mesures"]["nombre_pages"], 2)

    def test_la_page_dentree_doit_repondre(self):
        session = FausseSession({})

        with self.assertRaises(ErreurCollecte):
            collecter_site("https://exemple.ml/", session=session)

    def test_si_robots_txt_bloque_toutes_les_pages_on_le_signale_clairement(self):
        site = dict(PETIT_SITE)
        site["https://exemple.ml/robots.txt"] = b"User-agent: *\nDisallow: /\n"

        with self.assertRaises(ErreurCollecte) as souleve:
            collecter_site("https://exemple.ml/", session=FausseSession(site))

        self.assertIn("Aucune page n'a pu être analysée", str(souleve.exception))

    def test_une_redirection_ne_fait_pas_visiter_deux_fois_la_meme_page(self):
        """Vu sur un vrai site : surveylama.com redirige vers /en, et la page
        d'accueil était comptée deux fois dans la moyenne."""
        session = FausseSession(
            dict(PETIT_SITE),
            redirections={"https://exemple.ml": "https://exemple.ml/"},
        )

        resultat = collecter_site("https://exemple.ml", session=session)

        self.assertEqual(resultat["mesures"]["nombre_pages"], 3)
        self.assertEqual(len(set(resultat["pages"])), 3)

    def test_deux_adresses_qui_menent_a_la_meme_page_ne_comptent_quune_fois(self):
        """Vu sur un vrai site : surveylama.com et surveylama.com/ aboutissent
        toutes deux à /en, et l'accueil pesait deux fois dans la moyenne."""
        accueil = (
            '<html><body><a href="/contact">Contact</a>'
            '<a href="/accueil">Accueil</a></body></html>'
        )
        site = {
            "https://exemple.ml/": accueil.encode("utf-8"),
            "https://exemple.ml/contact": b"<html><body><p>Contact</p></body></html>",
        }
        session = FausseSession(
            site, redirections={"https://exemple.ml/accueil": "https://exemple.ml/"}
        )

        resultat = collecter_site("https://exemple.ml/", session=session)

        self.assertEqual(resultat["mesures"]["nombre_pages"], 2)
        self.assertEqual(
            sorted(resultat["pages"]),
            ["https://exemple.ml/", "https://exemple.ml/contact"],
        )

    def test_une_page_seule_annonce_une_page(self):
        """En audit d'une page, l'indicateur existe aussi et vaut 1."""
        session = FausseSession(dict(PETIT_SITE))

        resultat = collecter("https://exemple.ml/", session=session)

        self.assertEqual(resultat["mesures"]["nombre_pages"], 1)


class GardeFouAdresseTest(TestCase):
    """Le serveur ne doit pas pouvoir être utilisé pour visiter son réseau."""

    def test_adresse_de_bouclage_refusee(self):
        for adresse in ("http://127.0.0.1/", "http://localhost:8000/admin/"):
            with self.subTest(adresse=adresse):
                with self.assertRaises(ErreurCollecte):
                    verifier_adresse(adresse)

    def test_adresse_de_reseau_prive_refusee(self):
        for adresse in ("http://192.168.1.1/", "http://10.0.0.5/"):
            with self.subTest(adresse=adresse):
                with self.assertRaises(ErreurCollecte):
                    verifier_adresse(adresse)

    def test_protocole_fichier_refuse(self):
        with self.assertRaises(ErreurCollecte):
            verifier_adresse("file:///C:/Windows/win.ini")

    def test_domaine_introuvable_explique(self):
        with patch(
            "analyses.collecteur.socket.getaddrinfo", side_effect=__import__("socket").gaierror
        ):
            with self.assertRaises(ErreurCollecte) as souleve:
                verifier_adresse("https://domaine-qui-nexiste-pas.invalid/")

        self.assertIn("introuvable", str(souleve.exception))

    def test_adresse_publique_acceptee(self):
        with patch(
            "analyses.collecteur.socket.getaddrinfo",
            return_value=[(2, 1, 6, "", ("93.184.216.34", 0))],
        ):
            verifier_adresse("https://exemple.ml/")  # ne lève rien


class CatalogueTest(TestCase):
    def test_chaque_categorie_du_catalogue_existe(self):
        categories = set(RegleAnalyse.Categorie.values)
        for code, (_libelle, _unite, categorie) in CATALOGUE.items():
            with self.subTest(indicateur=code):
                self.assertIn(categorie, categories)

    def test_chaque_regle_du_referentiel_est_au_catalogue(self):
        Referentiel().handle()
        for code in RegleAnalyse.objects.values_list("code", flat=True):
            with self.subTest(regle=code):
                self.assertIn(code, CATALOGUE)


class AnalyseAvecCollecteTest(TestCase):
    """Le pont entre le collecteur et les modèles."""

    @classmethod
    def setUpTestData(cls):
        Referentiel().handle()
        utilisatrice = Utilisateur.objects.create_user(
            username="aicha", email="aicha@example.com", password="motdepasse-de-test"
        )
        cls.projet = Projet.objects.create(
            utilisateur=utilisatrice, nom="Mairie", url="https://exemple.ml/"
        )

    def collecte_simulee(self):
        return patch(
            "analyses.collecteur.collecter",
            return_value={
                "url_finale": "https://exemple.ml/",
                "mesures": {
                    "poids_total": 1850,
                    "nombre_requetes": 62,
                    "temps_chargement": 4.2,
                    "donnees_transferees": 1.81,
                    "poids_images": 650,
                },
                "ressources": [
                    {
                        "url": "https://exemple.ml/banniere.jpg",
                        "type": "image",
                        "taille": 380,
                        "optimisable": True,
                    }
                ],
            },
        )

    def test_sans_mesure_saisie_lanalyse_va_chercher_le_site(self):
        analyse = self.projet.lancer_analyse()

        with self.collecte_simulee():
            analyse.executer_analyse()

        self.assertEqual(analyse.indicateurs.count(), 5)
        self.assertEqual(analyse.ressources.count(), 1)
        self.assertEqual(analyse.rapport.poids_total, 1850)
        self.assertEqual(analyse.rapport.nombre_requetes, 62)
        self.assertEqual(analyse.rapport.temps_chargement, 4.2)
        self.assertTrue(analyse.problemes.exists())

    def test_les_indicateurs_recoivent_unite_et_categorie_du_catalogue(self):
        analyse = self.projet.lancer_analyse()

        with self.collecte_simulee():
            analyse.collecter_mesures()

        poids = analyse.indicateurs.get(nom="poids_total")
        self.assertEqual(poids.unite, "Ko")
        self.assertEqual(poids.categorie, RegleAnalyse.Categorie.POIDS)
        temps = analyse.indicateurs.get(nom="temps_chargement")
        self.assertEqual(temps.unite, "s")
        self.assertEqual(temps.categorie, RegleAnalyse.Categorie.RESEAU)

    def test_une_mesure_saisie_a_la_main_desactive_la_collecte(self):
        analyse = self.projet.lancer_analyse()
        Indicateur.objects.create(
            analyse=analyse,
            nom="poids_total",
            valeur=300,
            unite="Ko",
            categorie=RegleAnalyse.Categorie.POIDS,
        )

        with patch("analyses.collecteur.collecter") as faux_collecteur:
            analyse.executer_analyse()

        faux_collecteur.assert_not_called()
        self.assertEqual(analyse.indicateurs.count(), 1)
        self.assertEqual(analyse.score_global, 100.0)

    def test_le_choix_site_complet_declenche_le_parcours(self):
        analyse = self.projet.lancer_analyse(
            configuration={"type_audit": "site_complet", "mode_analyse": "approfondi"}
        )
        reponse = {
            "url_finale": "https://exemple.ml/",
            "mesures": {"poids_total": 900, "nombre_pages": 12},
            "ressources": [],
            "pages": [],
        }

        with patch("analyses.collecteur.collecter") as une_page, patch(
            "analyses.collecteur.collecter_site", return_value=reponse
        ) as tout_le_site:
            analyse.collecter_mesures()

        une_page.assert_not_called()
        tout_le_site.assert_called_once()
        # Le mode « approfondi » relève les plafonds.
        self.assertEqual(tout_le_site.call_args.kwargs["max_pages"], 15)
        self.assertEqual(tout_le_site.call_args.kwargs["max_ressources"], 60)
        self.assertEqual(analyse.indicateurs.get(nom="nombre_pages").valeur, 12)

    def test_le_choix_une_seule_page_reste_sur_une_page(self):
        analyse = self.projet.lancer_analyse(
            configuration={"type_audit": "page_unique", "mode_analyse": "rapide"}
        )

        with patch("analyses.collecteur.collecter_site") as tout_le_site, patch(
            "analyses.collecteur.collecter",
            return_value={
                "url_finale": "https://exemple.ml/",
                "mesures": {"poids_total": 900, "nombre_pages": 1},
                "ressources": [],
                "liens": [],
            },
        ) as une_page:
            analyse.collecter_mesures()

        tout_le_site.assert_not_called()
        # Le mode « rapide » abaisse le plafond de fichiers.
        self.assertEqual(une_page.call_args.kwargs["max_ressources"], 30)

    def test_site_injoignable_laisse_lanalyse_en_echec(self):
        analyse = self.projet.lancer_analyse()

        with patch(
            "analyses.collecteur.collecter",
            side_effect=ErreurCollecte("Le site n'a pas répondu."),
        ):
            with self.assertRaises(ErreurCollecte):
                analyse.executer_analyse()

        analyse.refresh_from_db()
        self.assertEqual(analyse.statut, Analyse.Statut.ECHOUEE)
        self.assertEqual(analyse.indicateurs.count(), 0)


class LancementDepuisLaPageTest(TestCase):
    """Le parcours complet : on colle une adresse, on clique, on obtient des chiffres."""

    @classmethod
    def setUpTestData(cls):
        Referentiel().handle()
        cls.utilisatrice = Utilisateur.objects.create_user(
            username="aicha", email="aicha@example.com", password="motdepasse-de-test"
        )
        cls.projet = Projet.objects.create(
            utilisateur=cls.utilisatrice, nom="Mairie", url="https://exemple.ml/"
        )

    def setUp(self):
        self.client.force_login(self.utilisatrice)

    def formulaire_vide(self):
        return {
            "type_audit": "page_unique",
            "mode_analyse": "rapide",
            "inclure_medias": "on",
            "inclure_javascript": "on",
            "type_appareil": "mobile_bas",
            "qualite_connexion": "3g",
            "forfait_data": "limite",
            # aucune mesure : c'est le cas qui posait problème
        }

    def test_formulaire_sans_mesure_declenche_la_mesure_automatique(self):
        with patch(
            "analyses.collecteur.collecter",
            return_value={
                "url_finale": "https://exemple.ml/",
                "mesures": {"poids_total": 1850, "nombre_requetes": 62, "temps_chargement": 4.2},
                "ressources": [],
            },
        ):
            reponse = self.client.post(
                reverse_lancer(self.projet.pk), self.formulaire_vide(), follow=True
            )

        analyse = Analyse.objects.get(projet=self.projet)
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(analyse.statut, Analyse.Statut.TERMINEE)
        self.assertEqual(analyse.rapport.poids_total, 1850)
        self.assertEqual(analyse.rapport.nombre_requetes, 62)
        self.assertContains(reponse, "1850")

    def test_message_clair_si_le_site_ne_repond_pas(self):
        with patch(
            "analyses.collecteur.collecter",
            side_effect=ErreurCollecte("Le domaine « exemple.ml » est introuvable."),
        ):
            reponse = self.client.post(
                reverse_lancer(self.projet.pk), self.formulaire_vide(), follow=True
            )

        self.assertContains(reponse, "Mesure impossible")
        self.assertContains(reponse, "introuvable")
        self.assertEqual(
            Analyse.objects.get(projet=self.projet).statut, Analyse.Statut.ECHOUEE
        )


def reverse_lancer(pk):
    from django.urls import reverse

    return reverse("lancer_analyse", args=[pk])
