"""Tests des comptes et vérification que l'administration s'ouvre vraiment.

Pour les lancer :  python manage.py test comptes
"""

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
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

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_envoyer_envoie_un_email_avec_le_message(self):
        utilisateur = Utilisateur.objects.create_user(
            username="aicha", email="aicha@example.com", password="motdepasse-de-test"
        )

        Notification.envoyer(utilisateur, "Analyse terminée")

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["aicha@example.com"])
        self.assertIn("Analyse terminée", mail.outbox[0].body)
        self.assertIn("[Green Dev Africa]", mail.outbox[0].subject)


class PagesDuCompteTest(TestCase):
    """Les pages de compte s'affichent et protègent l'accès aux comptes."""

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
        self.assertContains(reponse, 'class="nav-notifications"')
        self.assertContains(reponse, 'class="tableau-responsive notifications-tableau"')
        self.assertContains(reponse, 'data-label="Message"')
        self.assertContains(reponse, "Tout marquer comme lu")

    def test_page_du_profil(self):
        reponse = self.client.get(reverse("profil"))

        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "aicha")
        self.assertContains(reponse, 'class="nav-compte"')
        self.assertContains(reponse, 'aria-label="Mon compte — aicha"')
        self.assertContains(reponse, 'aria-current="page"')
        self.assertContains(reponse, f'action="{reverse("deconnexion")}"')
        self.assertContains(reponse, "Se déconnecter")
        self.assertContains(reponse, "Détails du compte")
        self.assertContains(reponse, "aicha@example.com")
        self.assertNotContains(reponse, "Enregistrer les modifications")
        self.assertNotContains(reponse, '<form method="post">')

    def test_navigation_indique_la_page_active(self):
        reponse = self.client.get(reverse("tableau_de_bord"))

        self.assertContains(reponse, 'aria-current="page"')
        self.assertNotContains(reponse, "Se déconnecter")

    def test_profil_est_en_lecture_seule(self):
        reponse = self.client.post(
            reverse("profil"), {"nom": "Aïcha D.", "email": "nouvelle@example.com"}
        )

        self.assertEqual(reponse.status_code, 405)
        self.utilisatrice.refresh_from_db()
        self.assertEqual(self.utilisatrice.nom, "Aïcha")
        self.assertEqual(self.utilisatrice.email, "aicha@example.com")

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

    def test_mot_de_passe_faible_ou_trop_court_refuse(self):
        reponse = self.creer("bamako2026")

        self.assertEqual(reponse.status_code, 200)
        self.assertFalse(Utilisateur.objects.filter(username="nouvelle").exists())

    def test_laide_du_formulaire_tient_en_une_phrase(self):
        reponse = self.client.get(reverse("inscription"))

        self.assertContains(reponse, "Au moins 12 caractères.")
        self.assertContains(reponse, 'placeholder="Ex. aicha-dembele"')
        self.assertContains(reponse, 'placeholder="Ex. Aïcha Dembélé"')
        self.assertContains(reponse, 'placeholder="Ex. aicha@exemple.com"')
        self.assertContains(reponse, 'placeholder="12 caractères minimum"')
        self.assertContains(reponse, 'placeholder="Répète ton mot de passe"')
        # Le pavé d'explications de Django a disparu.
        self.assertNotContains(reponse, "Votre mot de passe ne peut pas trop")

    def test_la_connexion_affiche_des_indices_dans_les_champs(self):
        reponse = self.client.get(reverse("connexion"))

        self.assertContains(reponse, 'placeholder="Ton identifiant"')
        self.assertContains(reponse, 'placeholder="Ton mot de passe"')
        self.assertContains(reponse, "Mot de passe oublié ?")
        self.assertContains(reponse, reverse("mot_de_passe_oublie"))

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_demande_de_reinitialisation_redirige_vers_la_page_envoyee(self):
        Utilisateur.objects.create_user(
            username="aicha",
            email="aicha@example.com",
            password="motdepasse-de-test",
        )

        reponse = self.client.post(
            reverse("mot_de_passe_oublie"),
            {"email": "aicha@example.com"},
        )

        self.assertRedirects(reponse, reverse("mot_de_passe_oublie_envoye"))

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


class PagesErreurTest(TestCase):
    """Les visiteurs voient des pages d'erreur en français, au style du site."""

    def test_page_404_en_francais(self):
        from django.test import override_settings

        with override_settings(DEBUG=False):
            reponse = self.client.get("/adresse-qui-n-existe-pas/")
        self.assertEqual(reponse.status_code, 404)
        self.assertContains(reponse, "Page introuvable", status_code=404)

    def test_page_500_rendue_sans_contexte(self):
        from django.template import loader

        html = loader.get_template("500.html").render()
        self.assertIn("Une erreur est survenue", html)


@override_settings(
    EMAIL_BACKEND="comptes.email_brevo.BrevoEmailBackend",
    BREVO_API_KEY="cle-de-test",
    DEFAULT_FROM_EMAIL="Green Dev Africa <contact@greendev.test>",
)
class EnvoiBrevoTest(TestCase):
    """Les e-mails partent par l'API HTTPS de Brevo, sans vrai appel réseau."""

    def _reponse(self, code=201, texte='{"messageId": "x"}'):
        from unittest.mock import Mock

        return Mock(status_code=code, text=texte)

    def test_message_converti_au_format_brevo(self):
        from unittest.mock import patch

        from django.core.mail import send_mail

        with patch("comptes.email_brevo.requests.post", return_value=self._reponse()) as post:
            envoyes = send_mail("Sujet", "Corps du message", None, ["Awa <awa@exemple.com>"])

        self.assertEqual(envoyes, 1)
        appel = post.call_args
        self.assertEqual(appel.args[0], "https://api.brevo.com/v3/smtp/email")
        self.assertEqual(appel.kwargs["headers"]["api-key"], "cle-de-test")
        self.assertEqual(
            appel.kwargs["json"],
            {
                "sender": {"email": "contact@greendev.test", "name": "Green Dev Africa"},
                "to": [{"email": "awa@exemple.com", "name": "Awa"}],
                "subject": "Sujet",
                "textContent": "Corps du message",
            },
        )
        self.assertEqual(appel.kwargs["timeout"], 10)

    def test_refus_de_brevo_remonte_une_erreur(self):
        from unittest.mock import patch

        from django.core.mail import send_mail

        from comptes.email_brevo import ErreurBrevo

        refus = self._reponse(400, '{"message": "sender not valid"}')
        with patch("comptes.email_brevo.requests.post", return_value=refus):
            with self.assertRaisesMessage(ErreurBrevo, "sender not valid"):
                send_mail("Sujet", "Corps", None, ["awa@exemple.com"])
            # fail_silently : pas d'exception, zéro envoi.
            self.assertEqual(
                send_mail("Sujet", "Corps", None, ["awa@exemple.com"], fail_silently=True),
                0,
            )

    def test_mot_de_passe_oublie_envoie_le_lien_par_brevo(self):
        from unittest.mock import patch

        get_user_model().objects.create_user(
            username="awa", email="awa@exemple.com", password="motdepasse-de-test", nom="Awa"
        )
        with patch("comptes.email_brevo.requests.post", return_value=self._reponse()) as post:
            reponse = self.client.post(
                reverse("mot_de_passe_oublie"), {"email": "awa@exemple.com"}
            )

        self.assertRedirects(reponse, reverse("mot_de_passe_envoye"))
        corps = post.call_args.kwargs["json"]
        self.assertEqual(corps["to"], [{"email": "awa@exemple.com"}])
        self.assertIn("/comptes/nouveau-mot-de-passe/", corps["textContent"])
        self.assertIn("Bonjour Awa", corps["textContent"])
