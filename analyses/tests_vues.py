"""Tests des vues des analyses : lancement, rapport, partage, comparaison, règles.

Pour les lancer :  python manage.py test analyses.tests_vues
"""

import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from analyses.management.commands.charger_referentiel import Command as Referentiel
from analyses.models import (
    Analyse,
    ComparaisonAnalyse,
    Indicateur,
    PartageRapport,
    Rapport,
    RegleAnalyse,
    RessourceWeb,
)
from projets.models import Projet

Utilisateur = get_user_model()
MOT_DE_PASSE = "motdepasse-de-test"


class BaseAnalyseVueTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        Referentiel().handle()
        cls.aicha = Utilisateur.objects.create_user(
            username="aicha", email="aicha@example.com", password=MOT_DE_PASSE, nom="Aïcha"
        )
        cls.fanta = Utilisateur.objects.create_user(
            username="fanta", email="fanta@example.com", password=MOT_DE_PASSE, nom="Fanta"
        )
        cls.projet = Projet.objects.create(
            utilisateur=cls.aicha, nom="Mon site", url="https://exemple.ml"
        )
        cls.projet_fanta = Projet.objects.create(
            utilisateur=cls.fanta, nom="Son site", url="https://autre.ml"
        )

    def setUp(self):
        self.client.force_login(self.aicha)

    def analyse_terminee(self, projet=None, poids=1600):
        projet = projet or self.projet
        analyse = projet.lancer_analyse()
        Indicateur.objects.create(
            analyse=analyse,
            nom="poids_total",
            valeur=poids,
            unite="Ko",
            categorie=RegleAnalyse.Categorie.POIDS,
        )
        analyse.executer_analyse()
        return analyse

    @staticmethod
    def donnees_formulaire(**remplacements):
        donnees = {
            "type_audit": "page_unique",
            "mode_analyse": "rapide",
            "inclure_medias": "on",
            "inclure_javascript": "on",
            "type_appareil": "mobile_bas",
            "qualite_connexion": "3g",
            "forfait_data": "limite",
            "mesure_poids_total": "1600",
        }
        donnees.update(remplacements)
        return donnees


class LancerAnalyseVueTest(BaseAnalyseVueTest):
    def test_le_formulaire_propose_un_champ_par_regle_active(self):
        reponse = self.client.get(reverse("lancer_analyse", args=[self.projet.pk]))

        self.assertEqual(reponse.status_code, 200)
        champs = list(reponse.context["formulaire"].champs_mesures())
        self.assertEqual(len(champs), RegleAnalyse.objects.filter(active=True).count())
        self.assertContains(reponse, "Poids total de la page")

    def test_une_regle_desactivee_disparait_du_formulaire(self):
        RegleAnalyse.objects.filter(code="poids_css").update(active=False)

        reponse = self.client.get(reverse("lancer_analyse", args=[self.projet.pk]))

        noms = [champ.name for champ in reponse.context["formulaire"].champs_mesures()]
        self.assertNotIn("mesure_poids_css", noms)

    def test_lancer_une_analyse_complete(self):
        reponse = self.client.post(
            reverse("lancer_analyse", args=[self.projet.pk]),
            self.donnees_formulaire(),
        )

        analyse = Analyse.objects.get(projet=self.projet)
        self.assertRedirects(reponse, reverse("analyse_detail", args=[analyse.pk]))
        self.assertEqual(analyse.statut, Analyse.Statut.TERMINEE)
        self.assertEqual(analyse.score_global, 80.0)
        self.assertEqual(analyse.indicateurs.count(), 1)
        self.assertEqual(analyse.problemes.count(), 1)
        self.assertTrue(Rapport.objects.filter(analyse=analyse).exists())
        # Les réglages du formulaire sont bien arrivés dans la base.
        self.assertEqual(analyse.contexte.qualite_connexion, "3g")
        self.assertEqual(analyse.configurations.first().mode_analyse, "rapide")

    def test_une_mesure_saisie_est_prise_telle_quelle(self):
        """Dès qu'une case est remplie, on ne va pas interroger le site.

        Le cas inverse — tout laisser vide pour déclencher la mesure
        automatique — est couvert dans `analyses/tests_collecteur.py`.
        """
        from unittest.mock import patch

        with patch("analyses.collecteur.collecter") as faux_collecteur:
            self.client.post(
                reverse("lancer_analyse", args=[self.projet.pk]),
                self.donnees_formulaire(),
            )

        faux_collecteur.assert_not_called()
        analyse = Analyse.objects.get(projet=self.projet)
        self.assertEqual(analyse.indicateurs.get().valeur, 1600)

    def test_mesure_negative_refusee(self):
        reponse = self.client.post(
            reverse("lancer_analyse", args=[self.projet.pk]),
            self.donnees_formulaire(mesure_poids_total="-5"),
        )

        self.assertEqual(reponse.status_code, 200)
        self.assertFalse(Analyse.objects.filter(projet=self.projet).exists())

    def test_impossible_danalyser_le_projet_dune_autre(self):
        reponse = self.client.post(
            reverse("lancer_analyse", args=[self.projet_fanta.pk]),
            self.donnees_formulaire(),
        )

        self.assertEqual(reponse.status_code, 404)
        self.assertFalse(Analyse.objects.filter(projet=self.projet_fanta).exists())


class AnalyseDetailVueTest(BaseAnalyseVueTest):
    def test_la_page_montre_probleme_recommandation_et_verdict(self):
        analyse = self.analyse_terminee()

        reponse = self.client.get(reverse("analyse_detail", args=[analyse.pk]))

        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "Poids des pages : 1600 Ko (maximum 500 Ko)")
        self.assertContains(reponse, "Alléger le poids de la page")
        self.assertContains(reponse, "Trop lourd pour ce contexte")
        self.assertFalse(reponse.context["compatible"])

    def test_les_indicateurs_portent_leur_nom_lisible(self):
        """Dans la page, « poids_total » devient « Poids total de la page »."""
        analyse = self.analyse_terminee()

        reponse = self.client.get(reverse("analyse_detail", args=[analyse.pk]))

        self.assertContains(reponse, "Poids total de la page")
        self.assertNotContains(reponse, ">poids_total<")

    def test_la_liste_des_fichiers_est_plafonnee_en_hauteur(self):
        """Elle peut compter des dizaines de lignes : elle défile au lieu
        d'étirer la page sur deux écrans."""
        analyse = self.analyse_terminee()
        RessourceWeb.objects.create(
            analyse=analyse,
            url="https://exemple.ml/gros.js",
            type=RessourceWeb.Type.SCRIPT,
            taille=400,
        )

        reponse = self.client.get(reverse("analyse_detail", args=[analyse.pk]))

        self.assertContains(reponse, "tableau-defilant")
        self.assertContains(reponse, "Fichiers téléchargés par la page (1)")

    def test_analyse_dune_autre_introuvable(self):
        analyse = self.analyse_terminee(projet=self.projet_fanta)

        reponse = self.client.get(reverse("analyse_detail", args=[analyse.pk]))

        self.assertEqual(reponse.status_code, 404)

    def test_recommandation_marquee_comme_faite(self):
        analyse = self.analyse_terminee()
        reco = analyse.problemes.get().recommandations.get()

        self.client.post(reverse("recommandation_faite", args=[reco.pk]))

        reco.refresh_from_db()
        self.assertEqual(reco.statut, "faite")
        # Plus aucune recommandation en attente : le problème passe corrigé.
        self.assertEqual(analyse.problemes.get().statut, "corrige")

    def test_recommandation_dune_autre_intouchable(self):
        analyse = self.analyse_terminee(projet=self.projet_fanta)
        reco = analyse.problemes.get().recommandations.get()

        reponse = self.client.post(reverse("recommandation_faite", args=[reco.pk]))

        self.assertEqual(reponse.status_code, 404)
        reco.refresh_from_db()
        self.assertEqual(reco.statut, "a_faire")


class RapportVueTest(BaseAnalyseVueTest):
    def test_page_du_rapport(self):
        analyse = self.analyse_terminee()

        reponse = self.client.get(reverse("rapport_detail", args=[analyse.pk]))

        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "Rapport de sobriété numérique")
        self.assertFalse(reponse.context["public"])

    def test_export_json(self):
        analyse = self.analyse_terminee()

        reponse = self.client.get(reverse("rapport_json", args=[analyse.pk]))

        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse["Content-Type"], "application/json")
        donnees = json.loads(reponse.content)
        self.assertEqual(donnees["green_score"], 80.0)
        self.assertEqual(donnees["poids_total_ko"], 1600)
        self.assertEqual(len(donnees["problemes"]), 1)

    def test_rapport_absent_renvoie_vers_lanalyse(self):
        analyse = Analyse.creer_pour(self.projet)

        reponse = self.client.get(reverse("rapport_detail", args=[analyse.pk]))

        self.assertRedirects(reponse, reverse("analyse_detail", args=[analyse.pk]))


class PartagePublicTest(BaseAnalyseVueTest):
    def test_creer_un_lien_puis_louvrir_sans_compte(self):
        analyse = self.analyse_terminee()

        self.client.post(
            reverse("rapport_partager", args=[analyse.pk]), {"duree_jours": "7"}
        )
        partage = PartageRapport.objects.get()

        self.client.logout()
        reponse = self.client.get(reverse("rapport_public", args=[partage.jeton]))

        self.assertEqual(reponse.status_code, 200)
        self.assertTrue(reponse.context["public"])
        self.assertContains(reponse, "Rapport de sobriété numérique")
        # La page publique ne propose pas de créer d'autres liens.
        self.assertNotContains(reponse, "Créer un lien public")

    def test_duree_hors_limites_ramenee_dans_les_bornes(self):
        analyse = self.analyse_terminee()

        self.client.post(
            reverse("rapport_partager", args=[analyse.pk]), {"duree_jours": "9999"}
        )

        partage = PartageRapport.objects.get()
        self.assertLessEqual(
            (partage.date_expiration - timezone.now()).days, 365
        )

    def test_duree_absurde_remplacee_par_la_valeur_par_defaut(self):
        analyse = self.analyse_terminee()

        self.client.post(
            reverse("rapport_partager", args=[analyse.pk]), {"duree_jours": "beaucoup"}
        )

        self.assertEqual(PartageRapport.objects.count(), 1)

    def test_lien_revoque_renvoie_410(self):
        analyse = self.analyse_terminee()
        partage = Rapport.objects.get(analyse=analyse).partager()

        self.client.post(reverse("partage_revoquer", args=[partage.pk]))
        self.client.logout()
        reponse = self.client.get(reverse("rapport_public", args=[partage.jeton]))

        self.assertEqual(reponse.status_code, 410)
        self.assertContains(reponse, "n'est plus valable", status_code=410)

    def test_lien_expire_renvoie_410(self):
        analyse = self.analyse_terminee()
        partage = Rapport.objects.get(analyse=analyse).partager()
        partage.date_expiration = timezone.now() - timezone.timedelta(days=1)
        partage.save()

        self.client.logout()
        reponse = self.client.get(reverse("rapport_public", args=[partage.jeton]))

        self.assertEqual(reponse.status_code, 410)

    def test_jeton_inconnu_renvoie_404(self):
        self.client.logout()

        reponse = self.client.get(reverse("rapport_public", args=["jeton-invente"]))

        self.assertEqual(reponse.status_code, 404)

    def test_partage_dune_autre_non_revocable(self):
        analyse = self.analyse_terminee(projet=self.projet_fanta)
        partage = Rapport.objects.get(analyse=analyse).partager()

        reponse = self.client.post(reverse("partage_revoquer", args=[partage.pk]))

        self.assertEqual(reponse.status_code, 404)
        self.assertTrue(PartageRapport.objects.get(pk=partage.pk).actif)


class ComparerVueTest(BaseAnalyseVueTest):
    def test_comparer_deux_analyses(self):
        avant = self.analyse_terminee(poids=1600)
        apres = self.analyse_terminee(poids=600)

        reponse = self.client.post(
            reverse("comparer", args=[self.projet.pk]),
            {"analyse_avant": avant.pk, "analyse_apres": apres.pk},
        )

        comparaison = ComparaisonAnalyse.objects.get()
        self.assertRedirects(
            reponse, reverse("comparaison_detail", args=[comparaison.pk])
        )
        self.assertEqual(comparaison.evolution, 18.0)

    def test_comparer_une_analyse_avec_elle_meme_est_refuse(self):
        analyse = self.analyse_terminee()

        reponse = self.client.post(
            reverse("comparer", args=[self.projet.pk]),
            {"analyse_avant": analyse.pk, "analyse_apres": analyse.pk},
        )

        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "deux analyses différentes")
        self.assertEqual(ComparaisonAnalyse.objects.count(), 0)

    def test_impossible_de_comparer_avec_lanalyse_dune_autre(self):
        mienne = self.analyse_terminee()
        sienne = self.analyse_terminee(projet=self.projet_fanta)

        reponse = self.client.post(
            reverse("comparer", args=[self.projet.pk]),
            {"analyse_avant": mienne.pk, "analyse_apres": sienne.pk},
        )

        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(ComparaisonAnalyse.objects.count(), 0)

    def test_page_de_resultat(self):
        avant = self.analyse_terminee(poids=1600)
        apres = self.analyse_terminee(poids=600)
        comparaison = ComparaisonAnalyse.objects.create(
            analyse_avant=avant, analyse_apres=apres
        )
        comparaison.comparer_resultats()

        reponse = self.client.get(
            reverse("comparaison_detail", args=[comparaison.pk])
        )

        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "Avant / après")


class ReglesSeuilsVueTest(BaseAnalyseVueTest):
    def test_une_developpeuse_na_pas_acces(self):
        reponse = self.client.get(reverse("regles_seuils"))

        self.assertEqual(reponse.status_code, 403)

    def test_une_administratrice_a_acces(self):
        self.aicha.role = Utilisateur.Role.ADMINISTRATEUR
        self.aicha.save()

        reponse = self.client.get(reverse("regles_seuils"))

        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "poids_total")

    def test_une_administratrice_modifie_un_seuil(self):
        self.aicha.role = Utilisateur.Role.ADMINISTRATEUR
        self.aicha.save()
        regles = RegleAnalyse.objects.order_by("categorie", "code")

        donnees = {
            "form-TOTAL_FORMS": str(regles.count()),
            "form-INITIAL_FORMS": str(regles.count()),
        }
        for index, regle in enumerate(regles):
            donnees[f"form-{index}-id"] = str(regle.pk)
            donnees[f"form-{index}-seuil"] = "250" if regle.code == "poids_total" else str(regle.seuil)
            if regle.active:
                donnees[f"form-{index}-active"] = "on"

        reponse = self.client.post(reverse("regles_seuils"), donnees)

        self.assertRedirects(reponse, reverse("regles_seuils"))
        self.assertEqual(RegleAnalyse.objects.get(code="poids_total").seuil, 250)

    def test_le_lien_regles_napparait_que_pour_les_administratrices(self):
        reponse = self.client.get(reverse("tableau_de_bord"))
        self.assertNotContains(reponse, "Règles d'analyse")

        self.aicha.role = Utilisateur.Role.ADMINISTRATEUR
        self.aicha.save()

        reponse = self.client.get(reverse("tableau_de_bord"))
        self.assertContains(reponse, "Règles d'analyse")


class InscriptionVueTest(TestCase):
    def test_creer_un_compte_et_etre_connectee(self):
        reponse = self.client.post(
            reverse("inscription"),
            {
                "username": "nouvelle",
                "nom": "Nouvelle Venue",
                "email": "nouvelle@example.com",
                "password1": "un-mot-de-passe-solide-42",
                "password2": "un-mot-de-passe-solide-42",
            },
        )

        self.assertRedirects(reponse, reverse("tableau_de_bord"))
        utilisatrice = Utilisateur.objects.get(username="nouvelle")
        self.assertEqual(utilisatrice.role, Utilisateur.Role.DEVELOPPEUR)
        self.assertEqual(
            int(self.client.session["_auth_user_id"]), utilisatrice.pk
        )

    def test_deux_comptes_ne_peuvent_pas_partager_une_adresse(self):
        Utilisateur.objects.create_user(
            username="premiere", email="pareil@example.com", password=MOT_DE_PASSE
        )

        reponse = self.client.post(
            reverse("inscription"),
            {
                "username": "seconde",
                "nom": "Seconde",
                "email": "pareil@example.com",
                "password1": "un-mot-de-passe-solide-42",
                "password2": "un-mot-de-passe-solide-42",
            },
        )

        self.assertEqual(reponse.status_code, 200)
        self.assertFalse(Utilisateur.objects.filter(username="seconde").exists())
