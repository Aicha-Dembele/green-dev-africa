"""Tests du « Mot de passe oublié ».

Pendant les tests, Django n'envoie aucun vrai e-mail : il les range dans
`mail.outbox`, une simple liste qu'on peut lire.
"""

import re

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse

Utilisateur = get_user_model()

ANCIEN = "ancien-mdp-2026"
NOUVEAU = "nouveau-mdp-2026"


def creer_aicha():
    return Utilisateur.objects.create_user(
        username="aicha", nom="Aïcha", email="aicha@example.com", password=ANCIEN
    )


def lien_du_message(message):
    """L'adresse du lien contenu dans l'e-mail, sans le nom du site."""
    return re.search(r"http://testserver(/\S+)", message.body).group(1)


class DemandeDuLienTest(TestCase):
    """Étapes 1 et 2 : on tape son adresse, le lien part (ou pas)."""

    def setUp(self):
        self.aicha = creer_aicha()

    def demander(self, email):
        return self.client.post(reverse("mot_de_passe_oublie"), {"email": email})

    def test_la_page_de_connexion_propose_le_lien(self):
        reponse = self.client.get(reverse("connexion"))
        self.assertContains(reponse, reverse("mot_de_passe_oublie"))
        self.assertContains(reponse, "Mot de passe oublié ?")

    def test_la_page_s_ouvre_sans_etre_connecte(self):
        reponse = self.client.get(reverse("mot_de_passe_oublie"))
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "Adresse e-mail de ton compte")

    def test_une_adresse_connue_recoit_le_lien(self):
        reponse = self.demander("aicha@example.com")
        self.assertRedirects(reponse, reverse("mot_de_passe_envoye"))
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["aicha@example.com"])
        self.assertEqual(message.subject, "Green Dev Africa : choisis un nouveau mot de passe")
        self.assertIn("Bonjour Aïcha,", message.body)
        self.assertIn("Ton identifiant de connexion : aicha", message.body)
        self.assertIn("valable 24 heures", message.body)
        self.assertTrue(lien_du_message(message).startswith("/comptes/nouveau-mot-de-passe/"))

    def test_l_email_est_du_texte_simple_sans_html(self):
        """Un e-mail léger, fidèle à la sobriété numérique : ni HTML ni image."""
        self.demander("aicha@example.com")
        self.assertEqual(mail.outbox[0].alternatives, [])
        self.assertNotIn("<", mail.outbox[0].body)

    def test_les_majuscules_tapees_ne_changent_rien(self):
        self.demander("AICHA@Example.COM")
        self.assertEqual([m.to for m in mail.outbox], [["aicha@example.com"]])

    def test_une_adresse_inconnue_n_envoie_rien_et_ne_le_dit_pas(self):
        """Même page que pour une vraie adresse : on ne révèle pas qui a un compte."""
        reponse = self.demander("inconnu@example.com")
        self.assertRedirects(reponse, reverse("mot_de_passe_envoye"))
        self.assertEqual(mail.outbox, [])

    def test_un_compte_desactive_ne_recoit_rien(self):
        self.aicha.is_active = False
        self.aicha.save()
        self.demander("aicha@example.com")
        self.assertEqual(mail.outbox, [])

    def test_la_page_envoye_dit_ou_chercher(self):
        reponse = self.client.get(reverse("mot_de_passe_envoye"))
        self.assertContains(reponse, "Regarde ta boîte e-mail")
        self.assertContains(reponse, "valable 24 heures")


class NouveauMotDePasseTest(TestCase):
    """Étapes 3 et 4 : le lien reçu permet de choisir un nouveau mot de passe."""

    def setUp(self):
        creer_aicha()
        self.client.post(reverse("mot_de_passe_oublie"), {"email": "aicha@example.com"})
        self.lien = lien_du_message(mail.outbox[0])

    def ouvrir_le_lien(self):
        """Ouvre le lien comme dans un navigateur ; renvoie la page et son adresse.

        Django retire aussitôt le jeton secret de l'adresse (il le garde dans
        la session), pour qu'il ne traîne pas dans l'historique du navigateur.
        """
        page = self.client.get(self.lien, follow=True)
        return page, page.redirect_chain[-1][0]

    def test_le_lien_recu_permet_de_changer_le_mot_de_passe(self):
        page, adresse = self.ouvrir_le_lien()
        self.assertContains(page, "Nouveau mot de passe")
        reponse = self.client.post(
            adresse, {"new_password1": NOUVEAU, "new_password2": NOUVEAU}
        )
        self.assertRedirects(reponse, reverse("mot_de_passe_change"))
        self.assertTrue(self.client.login(username="aicha", password=NOUVEAU))
        self.assertFalse(self.client.login(username="aicha", password=ANCIEN))

    def test_le_lien_ne_sert_qu_une_fois(self):
        _, adresse = self.ouvrir_le_lien()
        self.client.post(adresse, {"new_password1": NOUVEAU, "new_password2": NOUVEAU})
        reponse = self.client.get(self.lien, follow=True)
        self.assertContains(reponse, "Ce lien ne marche plus")
        self.assertNotContains(reponse, 'name="new_password1"')

    def test_un_lien_invente_est_refuse(self):
        reponse = self.client.get(
            reverse("mot_de_passe_nouveau", args=["MQ", "jeton-invente"])
        )
        self.assertContains(reponse, "Ce lien ne marche plus")
        self.assertContains(reponse, reverse("mot_de_passe_oublie"))

    def test_le_nouveau_mot_de_passe_suit_les_regles_de_l_inscription(self):
        _, adresse = self.ouvrir_le_lien()
        reponse = self.client.post(adresse, {"new_password1": "court", "new_password2": "court"})
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "trop court")
        self.assertTrue(self.client.login(username="aicha", password=ANCIEN))

    def test_les_deux_saisies_doivent_etre_identiques(self):
        _, adresse = self.ouvrir_le_lien()
        self.client.post(adresse, {"new_password1": NOUVEAU, "new_password2": "autre-mdp-2026"})
        self.assertTrue(self.client.login(username="aicha", password=ANCIEN))

    def test_la_page_finale_mene_a_la_connexion(self):
        reponse = self.client.get(reverse("mot_de_passe_change"))
        self.assertContains(reponse, "Mot de passe changé")
        self.assertContains(reponse, reverse("connexion"))
