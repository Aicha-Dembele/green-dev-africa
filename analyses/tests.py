"""Tests du moteur d'analyse : on vérifie la chaîne complète du diagramme.

    Projet → lancer_analyse() → indicateurs → executer_analyse()
          → problèmes → recommandations → score → rapport → notification

Pour les lancer :  python manage.py test analyses
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from analyses.management.commands.charger_referentiel import Command as Referentiel
from analyses.models import (
    Analyse,
    ComparaisonAnalyse,
    ConseilOptimisation,
    Indicateur,
    ProblemeDetecte,
    Rapport,
    Recommandation,
    RegleAnalyse,
    RessourceWeb,
)
from comptes.models import Notification
from projets.models import ObjectifOptimisation, Projet

Utilisateur = get_user_model()


class ChaineAnalyseTest(TestCase):
    """Une analyse complète, de la création du projet au rapport."""

    @classmethod
    def setUpTestData(cls):
        # Le référentiel est indispensable : sans règles, rien n'est détecté.
        Referentiel().handle()

        cls.utilisateur = Utilisateur.objects.create_user(
            username="aicha",
            email="aicha@example.com",
            password="motdepasse-de-test",
            nom="Aïcha Dembélé",
        )
        cls.projet = Projet.objects.create(
            utilisateur=cls.utilisateur,
            nom="Site vitrine de la clinique",
            url="https://exemple.ml",
        )

    def mesurer(self, analyse, **valeurs):
        """Simule ce que l'outil d'audit déposera comme indicateurs."""
        unites = {
            "poids_total": "Ko",
            "nombre_requetes": "requêtes",
            "temps_chargement": "s",
            "poids_images": "Ko",
        }
        for nom, valeur in valeurs.items():
            Indicateur.objects.create(
                analyse=analyse,
                nom=nom,
                valeur=valeur,
                unite=unites.get(nom, ""),
                categorie=RegleAnalyse.objects.get(code=nom).categorie,
            )

    # --- création de l'analyse ---

    def test_lancer_analyse_cree_configuration_et_contexte(self):
        """Les multiplicités 1..* et 1..1 du diagramme sont respectées."""
        analyse = self.projet.lancer_analyse(
            configuration={"mode_analyse": "approfondi"},
            contexte={"qualite_connexion": "2g"},
        )

        self.assertEqual(analyse.statut, Analyse.Statut.EN_ATTENTE)
        self.assertEqual(analyse.configurations.count(), 1)
        self.assertEqual(analyse.configurations.first().mode_analyse, "approfondi")
        self.assertEqual(analyse.contexte.qualite_connexion, "2g")

    # --- exécution ---

    def test_site_lourd_detecte_problemes_et_baisse_le_score(self):
        analyse = self.projet.lancer_analyse()
        self.mesurer(
            analyse,
            poids_total=1600,      # seuil 500  → dépassement x3,2 → critique
            nombre_requetes=45,    # seuil 40   → x1,12          → faible
            temps_chargement=6.5,  # seuil 3    → x2,16          → élevée
        )

        analyse.executer_analyse()
        analyse.refresh_from_db()

        self.assertEqual(analyse.statut, Analyse.Statut.TERMINEE)
        self.assertEqual(analyse.problemes.count(), 3)

        gravites = dict(analyse.problemes.values_list("regle__code", "gravite"))
        self.assertEqual(gravites["poids_total"], ProblemeDetecte.Gravite.CRITIQUE)
        self.assertEqual(gravites["nombre_requetes"], ProblemeDetecte.Gravite.FAIBLE)
        self.assertEqual(gravites["temps_chargement"], ProblemeDetecte.Gravite.ELEVEE)

        # 100 - (20 critique + 2 faible + 10 élevée) = 68
        self.assertEqual(analyse.score_global, 68.0)

    def test_site_sobre_ne_declenche_aucun_probleme(self):
        analyse = self.projet.lancer_analyse()
        self.mesurer(analyse, poids_total=320, nombre_requetes=18, temps_chargement=1.4)

        analyse.executer_analyse()

        self.assertEqual(analyse.problemes.count(), 0)
        self.assertEqual(analyse.score_global, 100.0)

    def test_chaque_probleme_recoit_une_recommandation(self):
        analyse = self.projet.lancer_analyse()
        self.mesurer(analyse, poids_total=1600, poids_images=900)

        analyse.executer_analyse()

        self.assertEqual(Recommandation.objects.count(), 2)
        reco = Recommandation.objects.get(categorie=RegleAnalyse.Categorie.IMAGES)
        self.assertEqual(reco.priorite, Recommandation.Priorite.URGENTE)
        # Le conseil est adapté : il cite l'URL analysée.
        self.assertIn("https://exemple.ml", reco.description)

    def test_rapport_reprend_les_indicateurs(self):
        analyse = self.projet.lancer_analyse()
        self.mesurer(analyse, poids_total=1600, nombre_requetes=45, temps_chargement=6.5)

        analyse.executer_analyse()
        rapport = Rapport.objects.get(analyse=analyse)

        self.assertEqual(rapport.poids_total, 1600)
        self.assertEqual(rapport.nombre_requetes, 45)
        self.assertEqual(rapport.temps_chargement, 6.5)
        self.assertEqual(rapport.green_score, analyse.score_global)

    def test_utilisateur_est_notifie_a_la_fin(self):
        analyse = self.projet.lancer_analyse()
        self.mesurer(analyse, poids_total=1600)

        analyse.executer_analyse()

        notification = Notification.objects.get(utilisateur=self.utilisateur)
        self.assertEqual(notification.type, Notification.Type.ANALYSE_TERMINEE)
        self.assertFalse(notification.lu)
        notification.marquer_comme_lue()
        self.assertTrue(Notification.objects.get(pk=notification.pk).lu)

    def test_analyse_echouee_si_une_etape_casse(self):
        """Le statut ne doit jamais rester bloqué sur « en cours »."""
        analyse = self.projet.lancer_analyse()
        self.mesurer(analyse, poids_total=1600)
        # On casse volontairement le calcul du score.
        analyse.calculer_score = lambda: 1 / 0

        with self.assertRaises(ZeroDivisionError):
            analyse.executer_analyse()

        analyse.refresh_from_db()
        self.assertEqual(analyse.statut, Analyse.Statut.ECHOUEE)


class GraviteTest(TestCase):
    """Les deux barèmes de gravité : règle de plafond et règle de comptage."""

    @classmethod
    def setUpTestData(cls):
        Referentiel().handle()
        utilisateur = Utilisateur.objects.create_user(
            username="kadia", email="kadia@example.com", password="motdepasse-de-test"
        )
        cls.projet = Projet.objects.create(
            utilisateur=utilisateur, nom="Journal", url="https://exemple.ml"
        )

    def gravite_pour(self, nom_regle, valeur):
        """Déclenche une seule règle et renvoie la gravité du problème créé."""
        regle = RegleAnalyse.objects.get(code=nom_regle)
        RegleAnalyse.objects.exclude(code=nom_regle).update(active=False)

        analyse = self.projet.lancer_analyse()
        Indicateur.objects.create(
            analyse=analyse,
            nom=nom_regle,
            valeur=valeur,
            unite="",
            categorie=regle.categorie,
        )
        analyse.executer_analyse()
        return analyse.problemes.get().gravite

    # --- règle de plafond : on juge le rapport valeur / seuil ---

    def test_plafond_depasse_de_peu(self):
        # poids_total : seuil 500 Ko
        self.assertEqual(
            self.gravite_pour("poids_total", 600), ProblemeDetecte.Gravite.FAIBLE
        )

    def test_plafond_depasse_une_fois_et_demie(self):
        self.assertEqual(
            self.gravite_pour("poids_total", 800), ProblemeDetecte.Gravite.MOYENNE
        )

    def test_plafond_depasse_deux_fois(self):
        self.assertEqual(
            self.gravite_pour("poids_total", 1100), ProblemeDetecte.Gravite.ELEVEE
        )

    def test_plafond_depasse_trois_fois(self):
        self.assertEqual(
            self.gravite_pour("poids_total", 1600), ProblemeDetecte.Gravite.CRITIQUE
        )

    # --- règle de comptage : on juge le nombre de cas ---

    def test_comptage_quelques_cas_reste_faible(self):
        """Le défaut corrigé : 2 images sans alternative n'est plus « Critique »."""
        # images_sans_alternative : seuil 0, donc règle de comptage
        self.assertEqual(
            self.gravite_pour("images_sans_alternative", 2),
            ProblemeDetecte.Gravite.FAIBLE,
        )

    def test_comptage_trois_cas_devient_moyen(self):
        self.assertEqual(
            self.gravite_pour("images_sans_alternative", 3),
            ProblemeDetecte.Gravite.MOYENNE,
        )

    def test_comptage_dix_cas_devient_eleve(self):
        self.assertEqual(
            self.gravite_pour("images_sans_alternative", 10),
            ProblemeDetecte.Gravite.ELEVEE,
        )

    def test_comptage_systematique_devient_critique(self):
        self.assertEqual(
            self.gravite_pour("images_sans_alternative", 25),
            ProblemeDetecte.Gravite.CRITIQUE,
        )

    # --- la nature de la règle, et le titre qui en découle ---

    def test_regle_de_comptage_reconnue_au_seuil_zero(self):
        self.assertTrue(
            RegleAnalyse.objects.get(code="images_sans_alternative").est_regle_de_comptage()
        )
        self.assertFalse(
            RegleAnalyse.objects.get(code="poids_total").est_regle_de_comptage()
        )

    def test_titre_du_probleme_dit_ce_quon_a_mesure(self):
        analyse = self.projet.lancer_analyse()
        Indicateur.objects.create(
            analyse=analyse,
            nom="poids_total",
            valeur=1600,
            unite="Ko",
            categorie=RegleAnalyse.Categorie.POIDS,
        )
        Indicateur.objects.create(
            analyse=analyse,
            nom="images_sans_alternative",
            valeur=4,
            unite="images",
            categorie=RegleAnalyse.Categorie.ACCESSIBILITE,
        )
        analyse.executer_analyse()

        titres = dict(analyse.problemes.values_list("regle__code", "titre"))
        self.assertEqual(
            titres["poids_total"],
            "Poids des pages : 1600 Ko (maximum 500 Ko)",
        )
        self.assertEqual(titres["images_sans_alternative"], "Accessibilité : 4 cas relevés")

    def test_les_nombres_a_virgule_sont_ecrits_a_la_francaise(self):
        analyse = self.projet.lancer_analyse()
        Indicateur.objects.create(
            analyse=analyse,
            nom="temps_chargement",
            valeur=4.95,
            unite="s",
            categorie=RegleAnalyse.Categorie.RESEAU,
        )
        analyse.executer_analyse()

        self.assertEqual(
            analyse.problemes.get().titre,
            "Réseau et cache : 4,95 s (maximum 3 s)",
        )


class ContexteUtilisateurTest(TestCase):
    """Le même site, jugé selon l'appareil et le réseau du visiteur."""

    @classmethod
    def setUpTestData(cls):
        Referentiel().handle()
        cls.utilisateur = Utilisateur.objects.create_user(
            username="moussa", email="moussa@example.com", password="motdepasse-de-test"
        )
        cls.projet = Projet.objects.create(
            utilisateur=cls.utilisateur, nom="Portail", url="https://exemple.ml"
        )

    def analyse_de(self, poids, connexion):
        analyse = self.projet.lancer_analyse(contexte={"qualite_connexion": connexion})
        Indicateur.objects.create(
            analyse=analyse,
            nom="poids_total",
            valeur=poids,
            unite="Ko",
            categorie=RegleAnalyse.Categorie.POIDS,
        )
        analyse.executer_analyse()
        return analyse

    def test_600_ko_passe_en_4g_mais_pas_en_2g(self):
        en_4g = self.analyse_de(600, "4g")
        en_2g = self.analyse_de(600, "2g")

        self.assertTrue(en_4g.contexte.evaluer_compatibilite())
        self.assertFalse(en_2g.contexte.evaluer_compatibilite())
        self.assertIn("300 Ko", en_2g.contexte.proposer_optimisation())

    def test_compatibilite_inconnue_sans_rapport(self):
        analyse = self.projet.lancer_analyse()
        self.assertIsNone(analyse.contexte.evaluer_compatibilite())


class RessourceWebTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        utilisateur = Utilisateur.objects.create_user(
            username="fanta", email="fanta@example.com", password="motdepasse-de-test"
        )
        projet = Projet.objects.create(
            utilisateur=utilisateur, nom="Blog", url="https://exemple.ml"
        )
        cls.analyse = Analyse.creer_pour(projet)
        cls.banniere = RessourceWeb.objects.create(
            analyse=cls.analyse,
            url="https://exemple.ml/banniere.png",
            type=RessourceWeb.Type.IMAGE,
            taille=900,
        )
        cls.style = RessourceWeb.objects.create(
            analyse=cls.analyse,
            url="https://exemple.ml/style.css",
            type=RessourceWeb.Type.STYLE,
            taille=100,
        )

    def test_part_dans_le_poids_total(self):
        self.assertEqual(self.banniere.calculer_poids(), 90.0)
        self.assertEqual(self.style.calculer_poids(), 10.0)

    def test_grosse_image_jugee_optimisable(self):
        self.assertTrue(self.banniere.verifier_optimisation())
        self.assertTrue(RessourceWeb.objects.get(pk=self.banniere.pk).optimisable)


class ComparaisonTest(TestCase):
    """Le cas d'utilisation « Comparer deux analyses (avant / après) »."""

    @classmethod
    def setUpTestData(cls):
        Referentiel().handle()
        utilisateur = Utilisateur.objects.create_user(
            username="sekou", email="sekou@example.com", password="motdepasse-de-test"
        )
        cls.projet = Projet.objects.create(
            utilisateur=utilisateur, nom="Boutique", url="https://exemple.ml"
        )

    def analyse_avec_poids(self, poids):
        analyse = self.projet.lancer_analyse()
        Indicateur.objects.create(
            analyse=analyse,
            nom="poids_total",
            valeur=poids,
            unite="Ko",
            categorie=RegleAnalyse.Categorie.POIDS,
        )
        analyse.executer_analyse()
        return analyse

    def test_evolution_apres_optimisation(self):
        avant = self.analyse_avec_poids(1600)  # critique → 80
        apres = self.analyse_avec_poids(600)   # faible   → 98

        comparaison = ComparaisonAnalyse.objects.create(
            analyse_avant=avant, analyse_apres=apres
        )
        comparaison.comparer_resultats()

        self.assertEqual(comparaison.score_avant, 80.0)
        self.assertEqual(comparaison.score_apres, 98.0)
        self.assertEqual(comparaison.evolution, 18.0)
        self.assertEqual(comparaison.ecart_poids, -1000.0)
        self.assertEqual(comparaison.taux_amelioration, 22.5)

    def test_taux_incalculable_si_le_score_de_depart_est_nul(self):
        """Un site qui casse toutes les règles tombe à 0 : pas de division par 0."""
        avant = self.analyse_avec_poids(1600)
        avant.score_global = 0.0
        avant.save(update_fields=["score_global"])
        apres = self.analyse_avec_poids(400)

        comparaison = ComparaisonAnalyse.objects.create(
            analyse_avant=avant, analyse_apres=apres
        )
        comparaison.comparer_resultats()

        self.assertEqual(comparaison.evolution, 100.0)
        self.assertIsNone(comparaison.taux_amelioration)


class PartageRapportTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        utilisateur = Utilisateur.objects.create_user(
            username="awa", email="awa@example.com", password="motdepasse-de-test"
        )
        projet = Projet.objects.create(
            utilisateur=utilisateur, nom="Vitrine", url="https://exemple.ml"
        )
        analyse = Analyse.creer_pour(projet)
        analyse.score_global = 72.0
        analyse.save()
        cls.rapport = Rapport.construire_depuis(analyse)

    def test_lien_valide_puis_revoque(self):
        partage = self.rapport.partager(duree_jours=7)

        self.assertTrue(partage.verifier_validite())
        self.assertEqual(len(partage.jeton), 43)  # token_urlsafe(32)

        partage.revoquer_lien()
        self.assertFalse(partage.verifier_validite())

    def test_lien_expire_nest_plus_valide(self):
        partage = self.rapport.partager()
        partage.date_expiration = timezone.now() - timezone.timedelta(days=1)
        partage.save()

        self.assertFalse(partage.verifier_validite())

    def test_export_json_contient_le_score(self):
        donnees = self.rapport.exporter_json()

        self.assertEqual(donnees["green_score"], 72.0)
        self.assertEqual(donnees["url"], "https://exemple.ml")
        self.assertEqual(donnees["problemes"], [])


class ObjectifTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        utilisateur = Utilisateur.objects.create_user(
            username="ibrahim", email="ibrahim@example.com", password="motdepasse-de-test"
        )
        cls.projet = Projet.objects.create(
            utilisateur=utilisateur, nom="Intranet", url="https://exemple.ml"
        )

    def test_objectif_atteint(self):
        objectif = ObjectifOptimisation.objects.create(
            projet=self.projet, nom="Page sous 500 Ko", valeur_cible=500
        )

        self.assertEqual(
            objectif.mettre_a_jour_progression(420), ObjectifOptimisation.Statut.ATTEINT
        )

    def test_objectif_rate_apres_la_date_limite(self):
        objectif = ObjectifOptimisation.objects.create(
            projet=self.projet,
            nom="Page sous 500 Ko",
            valeur_cible=500,
            date_limite=timezone.localdate() - timezone.timedelta(days=1),
        )

        self.assertEqual(
            objectif.mettre_a_jour_progression(900),
            ObjectifOptimisation.Statut.NON_ATTEINT,
        )

    def test_objectif_encore_en_cours(self):
        objectif = ObjectifOptimisation.objects.create(
            projet=self.projet,
            nom="Page sous 500 Ko",
            valeur_cible=500,
            date_limite=timezone.localdate() + timezone.timedelta(days=30),
        )

        self.assertEqual(
            objectif.mettre_a_jour_progression(900),
            ObjectifOptimisation.Statut.EN_COURS,
        )


class RegleEtConseilTest(TestCase):
    def test_regle_desactivee_est_ignoree(self):
        Referentiel().handle()
        RegleAnalyse.objects.filter(code="poids_total").update(active=False)

        utilisateur = Utilisateur.objects.create_user(
            username="bakary", email="bakary@example.com", password="motdepasse-de-test"
        )
        projet = Projet.objects.create(
            utilisateur=utilisateur, nom="Site", url="https://exemple.ml"
        )
        analyse = projet.lancer_analyse()
        Indicateur.objects.create(
            analyse=analyse,
            nom="poids_total",
            valeur=5000,
            unite="Ko",
            categorie=RegleAnalyse.Categorie.POIDS,
        )

        analyse.executer_analyse()

        self.assertEqual(analyse.problemes.count(), 0)
        self.assertEqual(analyse.score_global, 100.0)

    def test_referentiel_est_rejouable(self):
        Referentiel().handle()
        total_regles = RegleAnalyse.objects.count()
        total_conseils = ConseilOptimisation.objects.count()

        Referentiel().handle()

        self.assertEqual(RegleAnalyse.objects.count(), total_regles)
        self.assertEqual(ConseilOptimisation.objects.count(), total_conseils)
