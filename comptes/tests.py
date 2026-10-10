"""Tests des comptes et vérification que l'administration s'ouvre vraiment.

Pour les lancer :  python manage.py test comptes
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from comptes.models import Notification

Utilisateur = get_user_model()


class UtilisateurTest(TestCase):
    def test_role_par_defaut_developpeur(self):
        utilisateur = Utilisateur.objects.create_user(
            username="aicha", email="aicha@example.com", password="motdepasse-de-test"
        )

        self.assertEqual(utilisateur.role, Utilisateur.Role.DEVELOPPEUR)
        self.assertFalse(utilisateur.est_administrateur())

    def test_modifier_profil(self):
        utilisateur = Utilisateur.objects.create_user(
            username="aicha", email="aicha@example.com", password="motdepasse-de-test"
        )

        utilisateur.modifier_profil(nom="Aïcha D.", email="nouvelle@example.com")
        utilisateur.refresh_from_db()

        self.assertEqual(utilisateur.nom, "Aïcha D.")
        self.assertEqual(utilisateur.email, "nouvelle@example.com")

    def test_notification_marquee_comme_lue(self):
        utilisateur = Utilisateur.objects.create_user(
            username="aicha", email="aicha@example.com", password="motdepasse-de-test"
        )
        notification = Notification.envoyer(utilisateur, "Analyse terminée")

        self.assertFalse(notification.lu)
        notification.marquer_comme_lue()
        self.assertTrue(Notification.objects.get(pk=notification.pk).lu)


class PagesDuCompteTest(TestCase):
    """Les pages de compte s'affichent et le profil se modifie vraiment."""

    @classmethod
    def setUpTestData(cls):
        cls.utilisatrice = Utilisateur.objects.create_user(
            username="aicha",
            email="aicha@example.com",
            password="motdepasse-de-test",
            nom="Aïcha",
        )

    def setUp(self):
        self.client.force_login(self.utilisatrice)

    def test_page_des_notifications(self):
        Notification.envoyer(self.utilisatrice, "Analyse terminée")

        reponse = self.client.get(reverse("notifications"))

        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "Analyse terminée")

    def test_page_du_profil(self):
        reponse = self.client.get(reverse("profil"))

        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "aicha")

    def test_modifier_son_profil(self):
        reponse = self.client.post(
            reverse("profil"), {"nom": "Aïcha D.", "email": "nouvelle@example.com"}
        )

        self.assertRedirects(reponse, reverse("profil"))
        self.utilisatrice.refresh_from_db()
        self.assertEqual(self.utilisatrice.nom, "Aïcha D.")
        self.assertEqual(self.utilisatrice.email, "nouvelle@example.com")

    def test_se_deconnecter(self):
        reponse = self.client.post(reverse("deconnexion"))

        self.assertRedirects(reponse, reverse("connexion"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_se_connecter(self):
        self.client.logout()

        reponse = self.client.post(
            reverse("connexion"),
            {"username": "aicha", "password": "motdepasse-de-test"},
        )

        self.assertRedirects(reponse, reverse("tableau_de_bord"))


class MotDePasseTest(TestCase):
    """Les règles de mot de passe : deux, et faciles à satisfaire."""

    def creer(self, mot_de_passe):
        return self.client.post(
            reverse("inscription"),
            {
                "username": "nouvelle",
                "nom": "Nouvelle",
                "email": "nouvelle@example.com",
                "password1": mot_de_passe,
                "password2": mot_de_passe,
            },
        )

    def test_mot_de_passe_trop_court_refuse(self):
        reponse = self.creer("court12")  # 7 caractères

        self.assertEqual(reponse.status_code, 200)
        self.assertFalse(Utilisateur.objects.filter(username="nouvelle").exists())

    def test_mot_de_passe_entierement_chiffre_refuse(self):
        reponse = self.creer("123456789")

        self.assertEqual(reponse.status_code, 200)
        self.assertFalse(Utilisateur.objects.filter(username="nouvelle").exists())

    def test_mot_de_passe_simple_de_huit_caracteres_accepte(self):
        """« Mot de passe trop courant » ne bloque plus : c'était la règle
        qui rejetait des mots de passe raisonnables."""
        reponse = self.creer("bamako2026")

        self.assertRedirects(reponse, reverse("tableau_de_bord"))
        self.assertTrue(Utilisateur.objects.filter(username="nouvelle").exists())

    def test_laide_du_formulaire_tient_en_une_phrase(self):
        reponse = self.client.get(reverse("inscription"))

        self.assertContains(reponse, "Au moins 8 caractères.")
        # Le pavé d'explications de Django a disparu.
        self.assertNotContains(reponse, "Votre mot de passe ne peut pas trop")

    def test_le_petit_oeil_est_charge_sur_les_pages_de_mot_de_passe(self):
        for adresse in (reverse("inscription"), reverse("connexion")):
            with self.subTest(adresse=adresse):
                reponse = self.client.get(adresse)
                self.assertContains(reponse, "js/greendev.js")
                self.assertContains(reponse, 'type="password"')


class AdministrationTest(TestCase):
    """Chaque page de liste de l'admin doit s'afficher sans erreur.

    C'est le filet de sécurité du back-end : si un champ est mal nommé dans
    un admin.py, ce test le dit tout de suite.
    """

    MODELES = [
        ("comptes", "utilisateur"),
        ("comptes", "notification"),
        ("projets", "projet"),
        ("projets", "objectifoptimisation"),
        ("analyses", "analyse"),
        # ConfigurationAnalyse et UtilisateurContexte n'ont pas de page à eux :
        # ce sont des pièces de l'analyse, on les saisit dans sa fiche.
        ("analyses", "regleanalyse"),
        ("analyses", "conseiloptimisation"),
        ("analyses", "indicateur"),
        ("analyses", "ressourceweb"),
        ("analyses", "problemedetecte"),
        ("analyses", "recommandation"),
        ("analyses", "rapport"),
        ("analyses", "partagerapport"),
        ("analyses", "comparaisonanalyse"),
    ]

    @classmethod
    def setUpTestData(cls):
        cls.admin = Utilisateur.objects.create_superuser(
            username="admin-de-test",
            email="admin@example.com",
            password="motdepasse-de-test",
            nom="Administratrice",
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def test_accueil_admin(self):
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 200)

    def test_listes_et_formulaires_de_creation(self):
        for app, modele in self.MODELES:
            with self.subTest(modele=f"{app}.{modele}"):
                liste = self.client.get(reverse(f"admin:{app}_{modele}_changelist"))
                self.assertEqual(liste.status_code, 200)
                formulaire = self.client.get(reverse(f"admin:{app}_{modele}_add"))
                self.assertEqual(formulaire.status_code, 200)
