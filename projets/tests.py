"""Tests des vues des projets : affichage, création et cloisonnement.

Pour les lancer :  python manage.py test projets
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from analyses.management.commands.charger_referentiel import Command as Referentiel
from analyses.models import Analyse, Indicateur, ProblemeDetecte, RegleAnalyse
from projets.models import ObjectifOptimisation, Projet

Utilisateur = get_user_model()

MOT_DE_PASSE = "motdepasse-de-test"


class BaseProjetTest(TestCase):
    """Deux utilisatrices, chacune avec son projet : de quoi tester l'étanchéité."""

    @classmethod
    def setUpTestData(cls):
        Referentiel().handle()

        cls.aicha = Utilisateur.objects.create_user(
            username="aicha", email="aicha@example.com", password=MOT_DE_PASSE, nom="Aïcha"
        )
        cls.fanta = Utilisateur.objects.create_user(
            username="fanta", email="fanta@example.com", password=MOT_DE_PASSE, nom="Fanta"
        )
        cls.projet_aicha = Projet.objects.create(
            utilisateur=cls.aicha, nom="Site d'Aïcha", url="https://aicha.example.ml"
        )
        cls.projet_fanta = Projet.objects.create(
            utilisateur=cls.fanta, nom="Site de Fanta", url="https://fanta.example.ml"
        )

    def connecter_aicha(self):
        self.client.force_login(self.aicha)


class AccesSansCompteTest(BaseProjetTest):
    """Aucune page de travail ne doit s'ouvrir sans connexion."""

    def test_pages_protegees_renvoient_vers_la_connexion(self):
        adresses = [
            reverse("tableau_de_bord"),
            reverse("projet_creer"),
            reverse("projet_detail", args=[self.projet_aicha.pk]),
            reverse("projet_modifier", args=[self.projet_aicha.pk]),
            reverse("lancer_analyse", args=[self.projet_aicha.pk]),
            reverse("comparer", args=[self.projet_aicha.pk]),
            reverse("notifications"),
            reverse("profil"),
            reverse("regles_seuils"),
        ]
        for adresse in adresses:
            with self.subTest(adresse=adresse):
                reponse = self.client.get(adresse)
                self.assertRedirects(
                    reponse, f"{reverse('connexion')}?next={adresse}"
                )


class TableauDeBordTest(BaseProjetTest):
    def test_je_ne_vois_que_mes_projets(self):
        self.connecter_aicha()

        reponse = self.client.get(reverse("tableau_de_bord"))

        self.assertEqual(reponse.status_code, 200)
        # On vérifie sur les adresses : Django échappe les apostrophes des
        # noms (« Site d'Aïcha » devient « Site d&#x27;Aïcha » dans la page).
        self.assertContains(reponse, "https://aicha.example.ml")
        self.assertNotContains(reponse, "https://fanta.example.ml")
        self.assertNotContains(reponse, "Site de Fanta")

    def test_chiffres_cles_du_tableau_de_bord(self):
        analyse = self.projet_aicha.lancer_analyse()
        Indicateur.objects.create(
            analyse=analyse,
            nom="poids_total",
            valeur=1600,
            unite="Ko",
            categorie=RegleAnalyse.Categorie.POIDS,
        )
        analyse.executer_analyse()
        self.connecter_aicha()

        reponse = self.client.get(reverse("tableau_de_bord"))

        self.assertEqual(reponse.context["nb_projets"], 1)
        self.assertEqual(reponse.context["score_moyen"], 80.0)
        self.assertEqual(reponse.context["problemes_ouverts"], 1)
        self.assertEqual(reponse.context["problemes_critiques"], 1)

    def test_les_problemes_des_autres_ne_sont_pas_comptes(self):
        analyse = self.projet_fanta.lancer_analyse()
        Indicateur.objects.create(
            analyse=analyse,
            nom="poids_total",
            valeur=5000,
            unite="Ko",
            categorie=RegleAnalyse.Categorie.POIDS,
        )
        analyse.executer_analyse()
        self.connecter_aicha()

        reponse = self.client.get(reverse("tableau_de_bord"))

        self.assertEqual(reponse.context["problemes_ouverts"], 0)

    def test_tableau_de_bord_ne_fait_pas_une_requete_par_projet(self):
        """Garde-fou contre le N+1 : le nombre de requêtes ne doit pas suivre
        le nombre de projets affichés."""
        for numero in range(5):
            projet = Projet.objects.create(
                utilisateur=self.aicha,
                nom=f"Projet {numero}",
                url=f"https://exemple{numero}.ml",
            )
            Analyse.objects.create(projet=projet, score_global=50)
        self.connecter_aicha()

        with self.assertNumQueries(5):
            # 1 session + 1 utilisateur + 1 projets + 1 agrégat problèmes
            # + 1 pastille des notifications. Pas de requête par ligne.
            self.client.get(reverse("tableau_de_bord"))


class ProjetDetailTest(BaseProjetTest):
    def test_le_projet_dune_autre_est_introuvable(self):
        self.connecter_aicha()

        reponse = self.client.get(reverse("projet_detail", args=[self.projet_fanta.pk]))

        self.assertEqual(reponse.status_code, 404)

    def test_ma_fiche_projet_saffiche(self):
        self.connecter_aicha()

        reponse = self.client.get(
            reverse("projet_detail", args=[self.projet_aicha.pk])
        )

        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "https://aicha.example.ml")

    def test_modifier_le_projet_dune_autre_est_impossible(self):
        self.connecter_aicha()

        reponse = self.client.post(
            reverse("projet_modifier", args=[self.projet_fanta.pk]),
            {"nom": "Détourné", "url": "https://pirate.ml", "statut": "actif", "description": ""},
        )

        self.assertEqual(reponse.status_code, 404)
        self.projet_fanta.refresh_from_db()
        self.assertEqual(self.projet_fanta.nom, "Site de Fanta")


class CreationProjetTest(BaseProjetTest):
    def test_creer_un_projet(self):
        self.connecter_aicha()

        reponse = self.client.post(
            reverse("projet_creer"),
            {
                "nom": "Nouveau site",
                "url": "https://nouveau.example.ml",
                "description": "Un essai",
                "statut": "actif",
            },
        )

        projet = Projet.objects.get(nom="Nouveau site")
        self.assertRedirects(reponse, reverse("projet_detail", args=[projet.pk]))
        self.assertEqual(projet.utilisateur, self.aicha)

    def test_le_proprietaire_ne_peut_pas_etre_force_par_le_formulaire(self):
        """Même en trafiquant la page, on ne crée pas un projet au nom d'autrui."""
        self.connecter_aicha()

        self.client.post(
            reverse("projet_creer"),
            {
                "nom": "Tentative",
                "url": "https://tentative.example.ml",
                "description": "",
                "statut": "actif",
                "utilisateur": self.fanta.pk,  # champ ajouté de force
            },
        )

        self.assertEqual(Projet.objects.get(nom="Tentative").utilisateur, self.aicha)

    def test_url_invalide_refusee(self):
        self.connecter_aicha()

        reponse = self.client.post(
            reverse("projet_creer"),
            {"nom": "Bancal", "url": "pas-une-adresse", "description": "", "statut": "actif"},
        )

        self.assertEqual(reponse.status_code, 200)
        self.assertFalse(Projet.objects.filter(nom="Bancal").exists())


class ObjectifTest(BaseProjetTest):
    def test_ajouter_un_objectif_depuis_la_fiche(self):
        self.connecter_aicha()

        reponse = self.client.post(
            reverse("objectif_creer", args=[self.projet_aicha.pk]),
            {"nom": "Sous 500 Ko", "valeur_cible": 500, "unite": "Ko", "date_limite": ""},
        )

        self.assertRedirects(
            reponse, reverse("projet_detail", args=[self.projet_aicha.pk])
        )
        self.assertEqual(self.projet_aicha.objectifs.count(), 1)

    def test_impossible_dajouter_un_objectif_au_projet_dune_autre(self):
        self.connecter_aicha()

        reponse = self.client.post(
            reverse("objectif_creer", args=[self.projet_fanta.pk]),
            {"nom": "Intrusion", "valeur_cible": 100, "unite": "Ko", "date_limite": ""},
        )

        self.assertEqual(reponse.status_code, 404)
        self.assertEqual(self.projet_fanta.objectifs.count(), 0)

    def test_supprimer_un_objectif(self):
        objectif = ObjectifOptimisation.objects.create(
            projet=self.projet_aicha, nom="À retirer", valeur_cible=500
        )
        self.connecter_aicha()

        self.client.post(
            reverse("objectif_supprimer", args=[self.projet_aicha.pk, objectif.pk])
        )

        self.assertFalse(
            ObjectifOptimisation.objects.filter(pk=objectif.pk).exists()
        )


class NotificationsVueTest(BaseProjetTest):
    def test_la_pastille_compte_mes_notifications_non_lues(self):
        analyse = self.projet_aicha.lancer_analyse()
        Indicateur.objects.create(
            analyse=analyse,
            nom="poids_total",
            valeur=1600,
            unite="Ko",
            categorie=RegleAnalyse.Categorie.POIDS,
        )
        analyse.executer_analyse()
        self.connecter_aicha()

        reponse = self.client.get(reverse("tableau_de_bord"))

        self.assertEqual(reponse.context["notifications_non_lues"], 1)

    def test_tout_marquer_comme_lu(self):
        from comptes.models import Notification

        Notification.envoyer(self.aicha, "Un message")
        Notification.envoyer(self.aicha, "Un autre")
        self.connecter_aicha()

        self.client.post(reverse("notifications_toutes_lues"))

        self.assertEqual(self.aicha.notifications.filter(lu=False).count(), 0)

    def test_impossible_de_marquer_la_notification_dune_autre(self):
        from comptes.models import Notification

        notification = Notification.envoyer(self.fanta, "Message privé")
        self.connecter_aicha()

        reponse = self.client.post(
            reverse("notification_lue", args=[notification.pk])
        )

        self.assertEqual(reponse.status_code, 404)
        self.assertFalse(Notification.objects.get(pk=notification.pk).lu)


class ProblemeStatutVueTest(BaseProjetTest):
    def test_changer_le_statut_dun_probleme(self):
        analyse = self.projet_aicha.lancer_analyse()
        Indicateur.objects.create(
            analyse=analyse,
            nom="poids_total",
            valeur=1600,
            unite="Ko",
            categorie=RegleAnalyse.Categorie.POIDS,
        )
        analyse.executer_analyse()
        probleme = analyse.problemes.get()
        self.connecter_aicha()

        self.client.post(
            reverse("probleme_statut", args=[probleme.pk]),
            {"statut": ProblemeDetecte.Statut.CORRIGE},
        )

        probleme.refresh_from_db()
        self.assertEqual(probleme.statut, ProblemeDetecte.Statut.CORRIGE)

    def test_statut_inconnu_refuse(self):
        analyse = self.projet_aicha.lancer_analyse()
        Indicateur.objects.create(
            analyse=analyse,
            nom="poids_total",
            valeur=1600,
            unite="Ko",
            categorie=RegleAnalyse.Categorie.POIDS,
        )
        analyse.executer_analyse()
        probleme = analyse.problemes.get()
        self.connecter_aicha()

        self.client.post(
            reverse("probleme_statut", args=[probleme.pk]), {"statut": "n-importe-quoi"}
        )

        probleme.refresh_from_db()
        self.assertEqual(probleme.statut, ProblemeDetecte.Statut.OUVERT)
