from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from analyses.models import Analyse, ConfigurationAnalyse
from credits import config as credits_config
from credits.config import (
    COUT_PAGE_HORS_QUOTA,
    CREDITS_BIENVENUE,
    MONTANTS_SUGGERES,
    PRIX_CREDIT_FCFA,
    QUOTA_GRATUIT_MENSUEL,
    TEXTE_OBTENIR_CREDITS,
    TYPE_AUDIT_PAGE_UNIQUE,
    credits_pour_montant,
    montant_pour_credits,
)
from credits.models import JournalCredits, SoldeCredits
from credits.services import (
    acheter_credits,
    ajouter_credits,
    attribuer_credits_bienvenue,
    calculer_cout,
    compter_analyses_gratuites_du_mois,
    debiter_pour_analyse,
    rembourser_analyse,
)
from projets.models import Projet

Utilisateur = get_user_model()


class CreditsMetierTest(TestCase):
    def creer_analyse(self, utilisateur, type_audit=ConfigurationAnalyse.TypeAudit.PAGE_UNIQUE):
        projet = Projet.objects.create(
            utilisateur=utilisateur,
            nom=f"Projet {utilisateur.username}",
            url="https://exemple.ml",
        )
        analyse = Analyse.objects.create(
            projet=projet,
            statut=Analyse.Statut.TERMINEE,
        )
        ConfigurationAnalyse.objects.create(
            analyse=analyse,
            type_audit=type_audit,
            mode_analyse=ConfigurationAnalyse.Mode.RAPIDE,
        )
        return analyse

    def test_acheter_credits_ajoute_une_transaction_et_met_a_jour_le_solde(self):
        utilisateur = Utilisateur.objects.create_user(
            username="aicha_achat",
            email="aicha-achat@example.com",
            password="Passw0rd!123",
            nom="Aïcha",
        )

        transaction = acheter_credits(utilisateur, 25, "Achat de 25 crédits")

        self.assertEqual(transaction.montant, 25)
        self.assertEqual(transaction.type, JournalCredits.Type.ACHAT_MANUEL)
        self.assertEqual(SoldeCredits.objects.get(utilisateur=utilisateur).solde, CREDITS_BIENVENUE + 25)

    def test_debit_normal(self):
        utilisateur = Utilisateur.objects.create_user(
            username="aicha_achat_2",
            email="aicha-achat-2@example.com",
            password="motdepasse-de-test",
            nom="Aïcha",
        )
        ajouter_credits(utilisateur, 15, JournalCredits.Type.AJUSTEMENT_ADMIN, "test")

        analyse = self.creer_analyse(utilisateur)
        ok = debiter_pour_analyse(utilisateur, analyse, 5)

        self.assertTrue(ok)
        self.assertEqual(
            JournalCredits.objects.filter(
                utilisateur=utilisateur,
                analyse=analyse,
                type=JournalCredits.Type.DEBIT_ANALYSE,
            ).count(),
            1,
        )
        self.assertEqual(
            JournalCredits.objects.get(
                utilisateur=utilisateur,
                analyse=analyse,
                type=JournalCredits.Type.DEBIT_ANALYSE,
            ).montant,
            -5,
        )
        self.assertEqual(SoldeCredits.objects.get(utilisateur=utilisateur).solde, 20)

    def test_solde_insuffisant_refuse_le_debit(self):
        utilisateur = Utilisateur.objects.create_user(
            username="binta",
            email="binta@example.com",
            password="motdepasse-de-test",
            nom="Binta",
        )
        ajouter_credits(utilisateur, 2, JournalCredits.Type.AJUSTEMENT_ADMIN, "test")
        analyse = self.creer_analyse(utilisateur)

        ok = debiter_pour_analyse(utilisateur, analyse, 25)

        self.assertFalse(ok)
        self.assertEqual(
            JournalCredits.objects.filter(
                utilisateur=utilisateur,
                analyse=analyse,
                type=JournalCredits.Type.DEBIT_ANALYSE,
            ).count(),
            0,
        )

    def test_double_debit_refuse(self):
        utilisateur = Utilisateur.objects.create_user(
            username="sita",
            email="sita@example.com",
            password="motdepasse-de-test",
            nom="Sita",
        )
        ajouter_credits(utilisateur, 10, JournalCredits.Type.AJUSTEMENT_ADMIN, "test")
        analyse = self.creer_analyse(utilisateur)

        self.assertTrue(debiter_pour_analyse(utilisateur, analyse, 5))
        self.assertFalse(debiter_pour_analyse(utilisateur, analyse, 5))
        self.assertEqual(
            JournalCredits.objects.filter(
                utilisateur=utilisateur,
                analyse=analyse,
                type=JournalCredits.Type.DEBIT_ANALYSE,
            ).count(),
            1,
        )

    def test_remboursement_est_idempotent(self):
        utilisateur = Utilisateur.objects.create_user(
            username="mariam",
            email="mariam@example.com",
            password="motdepasse-de-test",
            nom="Mariam",
        )
        ajouter_credits(utilisateur, 20, JournalCredits.Type.AJUSTEMENT_ADMIN, "test")
        analyse = self.creer_analyse(utilisateur)

        self.assertTrue(debiter_pour_analyse(utilisateur, analyse, 7))
        self.assertTrue(rembourser_analyse(analyse))
        self.assertFalse(rembourser_analyse(analyse))
        self.assertEqual(
            JournalCredits.objects.filter(
                utilisateur=utilisateur,
                analyse=analyse,
                type=JournalCredits.Type.REMBOURSEMENT,
            ).count(),
            1,
        )
        self.assertEqual(SoldeCredits.objects.get(utilisateur=utilisateur).solde, 30)

    def test_bienvenue_n_est_attribue_qu_une_fois(self):
        utilisateur = Utilisateur.objects.create_user(
            username="fatou",
            email="fatou@example.com",
            password="motdepasse-de-test",
            nom="Fatou",
        )

        self.assertEqual(
            JournalCredits.objects.filter(
                utilisateur=utilisateur,
                type=JournalCredits.Type.BIENVENUE,
            ).count(),
            1,
        )
        self.assertEqual(
            JournalCredits.objects.get(
                utilisateur=utilisateur,
                type=JournalCredits.Type.BIENVENUE,
            ).montant,
            CREDITS_BIENVENUE,
        )

        attribuer_credits_bienvenue(utilisateur)

        self.assertEqual(
            JournalCredits.objects.filter(
                utilisateur=utilisateur,
                type=JournalCredits.Type.BIENVENUE,
            ).count(),
            1,
        )
        self.assertEqual(SoldeCredits.objects.get(utilisateur=utilisateur).solde, CREDITS_BIENVENUE)

    def test_solde_est_egal_a_la_somme_du_journal(self):
        utilisateur = Utilisateur.objects.create_user(
            username="amina",
            email="amina@example.com",
            password="motdepasse-de-test",
            nom="Amina",
        )
        ajouter_credits(utilisateur, 12, JournalCredits.Type.AJUSTEMENT_ADMIN, "test")
        analyse = self.creer_analyse(utilisateur)
        debiter_pour_analyse(utilisateur, analyse, 4)

        solde = SoldeCredits.objects.get(utilisateur=utilisateur)
        total_journal = sum(
            ligne.montant for ligne in JournalCredits.objects.filter(utilisateur=utilisateur)
        )

        self.assertEqual(solde.solde, total_journal)
        ok, details = solde.verifier()
        self.assertTrue(ok)
        self.assertEqual(details["solde"], details["journal"])

    def test_quota_gratuit_se_vide_puis_devient_payant(self):
        utilisateur = Utilisateur.objects.create_user(
            username="moussa",
            email="moussa@example.com",
            password="motdepasse-de-test",
            nom="Moussa",
        )

        for _ in range(QUOTA_GRATUIT_MENSUEL):
            self.creer_analyse(utilisateur)

        self.assertEqual(compter_analyses_gratuites_du_mois(utilisateur), QUOTA_GRATUIT_MENSUEL)
        self.assertEqual(
            calculer_cout({"type_audit": TYPE_AUDIT_PAGE_UNIQUE}, utilisateur),
            COUT_PAGE_HORS_QUOTA,
        )

    def test_initialiser_credits_cree_les_soldes_manquants_et_attribue_bienvenue_une_fois(self):
        utilisateur = Utilisateur.objects.create_user(
            username="nour",
            email="nour@example.com",
            password="Test12345",
            nom="Nour",
        )
        SoldeCredits.objects.filter(utilisateur=utilisateur).delete()

        out = StringIO()
        call_command("initialiser_credits", stdout=out)

        self.assertTrue(SoldeCredits.objects.filter(utilisateur=utilisateur).exists())
        self.assertEqual(SoldeCredits.objects.get(utilisateur=utilisateur).solde, CREDITS_BIENVENUE)
        self.assertEqual(
            JournalCredits.objects.filter(
                utilisateur=utilisateur,
                type=JournalCredits.Type.BIENVENUE,
            ).count(),
            1,
        )

        call_command("initialiser_credits", stdout=out)
        self.assertEqual(
            JournalCredits.objects.filter(
                utilisateur=utilisateur,
                type=JournalCredits.Type.BIENVENUE,
            ).count(),
            1,
        )

    def test_initialiser_credits_dry_run_ne_modifie_pas_la_base(self):
        utilisateur = Utilisateur.objects.create_user(
            username="seynabou",
            email="seynabou@example.com",
            password="Test12345",
            nom="Seynabou",
        )
        SoldeCredits.objects.filter(utilisateur=utilisateur).delete()

        out = StringIO()
        call_command("initialiser_credits", dry_run=True, stdout=out)

        self.assertFalse(SoldeCredits.objects.filter(utilisateur=utilisateur).exists())
        self.assertIn("--dry-run", out.getvalue())

    def test_verifier_credits_signale_solde_absent_et_soldes_incoherents(self):
        utilisateur = Utilisateur.objects.create_user(
            username="oumar",
            email="oumar@example.com",
            password="Test12345",
            nom="Oumar",
        )
        SoldeCredits.objects.filter(utilisateur=utilisateur).delete()
        out = StringIO()
        call_command("verifier_credits", stdout=out)

        self.assertIn("AVERTISSEMENT", out.getvalue())

        solde, _ = SoldeCredits.objects.get_or_create(utilisateur=utilisateur)
        ajouter_credits(utilisateur, 5, JournalCredits.Type.AJUSTEMENT_ADMIN, "test")
        solde.refresh_from_db()
        solde.solde = 0
        solde.save(update_fields=["solde"])

        out = StringIO()
        call_command("verifier_credits", stdout=out)
        self.assertIn("ERREUR", out.getvalue())

    def test_echec_danalyze_rembourse_le_debit_et_restaure_le_solde(self):
        utilisateur = Utilisateur.objects.create_user(
            username="serigne",
            email="serigne@example.com",
            password="motdepasse-de-test",
            nom="Sérigne",
        )
        ajouter_credits(utilisateur, 20, JournalCredits.Type.AJUSTEMENT_ADMIN, "test")
        analyse = self.creer_analyse(utilisateur)

        self.assertTrue(debiter_pour_analyse(utilisateur, analyse, 5))

        with self.assertRaises(RuntimeError):
            with patch.object(Analyse, "collecter_mesures", side_effect=RuntimeError("bug collecte")):
                analyse.executer_analyse()

        analyse.refresh_from_db()
        self.assertEqual(analyse.statut, Analyse.Statut.ECHOUEE)
        self.assertEqual(
            JournalCredits.objects.filter(
                utilisateur=utilisateur,
                analyse=analyse,
                type=JournalCredits.Type.DEBIT_ANALYSE,
            ).count(),
            1,
        )
        remboursement = JournalCredits.objects.get(
            utilisateur=utilisateur,
            analyse=analyse,
            type=JournalCredits.Type.REMBOURSEMENT,
        )
        self.assertEqual(remboursement.montant, 5)
        self.assertEqual(SoldeCredits.objects.get(utilisateur=utilisateur).solde, 30)

    def test_analyse_bloquee_en_cours_est_liberee_et_remboursee(self):
        from datetime import timedelta

        from django.utils import timezone

        from analyses.management.commands.traiter_analyses import (
            liberer_analyses_bloquees,
        )

        utilisateur = Utilisateur.objects.create_user(
            username="bloquee",
            email="bloquee@example.com",
            password="motdepasse-de-test",
            nom="Bloquée",
        )
        ajouter_credits(utilisateur, 20, JournalCredits.Type.AJUSTEMENT_ADMIN, "test")
        ancienne = self.creer_analyse(utilisateur)
        self.assertTrue(debiter_pour_analyse(utilisateur, ancienne, 5))
        Analyse.objects.filter(pk=ancienne.pk).update(
            statut=Analyse.Statut.EN_COURS,
            date_analyse=timezone.now() - timedelta(hours=1),
        )
        recente = self.creer_analyse(utilisateur)
        Analyse.objects.filter(pk=recente.pk).update(statut=Analyse.Statut.EN_COURS)

        self.assertEqual(liberer_analyses_bloquees(utilisateur), 1)

        ancienne.refresh_from_db()
        recente.refresh_from_db()
        self.assertEqual(ancienne.statut, Analyse.Statut.ECHOUEE)
        self.assertEqual(recente.statut, Analyse.Statut.EN_COURS)
        self.assertEqual(SoldeCredits.objects.get(utilisateur=utilisateur).solde, 30)
        # Un second passage ne rembourse pas deux fois.
        self.assertEqual(liberer_analyses_bloquees(utilisateur), 0)
        self.assertEqual(SoldeCredits.objects.get(utilisateur=utilisateur).solde, 30)

    def test_tarifs_public_sont_accessibles_sans_compte(self):
        response = self.client.get(reverse("tarifs"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Tarifs")
        self.assertContains(response, str(QUOTA_GRATUIT_MENSUEL))
        self.assertContains(response, str(CREDITS_BIENVENUE))
        self.assertEqual(response.context["texte_obtenir_credits"], TEXTE_OBTENIR_CREDITS)
        self.assertContains(response, "Le paiement est simulé")

    def test_conversion_montant_fcfa_vers_credits_et_inverse(self):
        conversions_attendues = {
            1000: 20,
            2500: 50,
            5000: 100,
        }
        for montant, credits in conversions_attendues.items():
            with self.subTest(montant=montant):
                self.assertEqual(credits_pour_montant(montant), credits)
                self.assertEqual(montant_pour_credits(credits), montant)

    def test_conversion_refuse_les_montants_invalides_avec_un_message_lisible(self):
        montants_invalides = (999, 50500, 1250)
        for montant in montants_invalides:
            with self.subTest(montant=montant):
                with self.assertRaises(ValueError) as contexte:
                    credits_pour_montant(montant)
                self.assertTrue(str(contexte.exception))
                self.assertIn("montant", str(contexte.exception).lower())

    def test_calculateur_tarifs_affiche_les_erreurs_en_francais(self):
        response = self.client.get(reverse("tarifs"), {"montant": 999})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Le montant minimum est de 1000 FCFA.")
        self.assertIsNone(response.context["resultat_calcul"])


@override_settings(BETA_SIMULATED_PAYMENTS=True)
class ParcoursAchatTest(TestCase):
    """Le tunnel d'achat simulé : montant → paiement → code → reçu."""

    def setUp(self):
        self.utilisateur = Utilisateur.objects.create_user(
            username="awa_achat",
            email="awa-achat@example.com",
            password="motdepasse-de-test",
            nom="Awa",
        )
        self.client.force_login(self.utilisateur)

    def solde(self):
        return SoldeCredits.objects.get(utilisateur=self.utilisateur).solde

    def commander(self, montant=2500):
        from credits.models import CommandeCredits

        reponse = self.client.post(reverse("acheter_credits"), {"montant": montant})
        commande = CommandeCredits.objects.get(utilisateur=self.utilisateur)
        self.assertRedirects(
            reponse, reverse("commande_paiement", args=[commande.reference]),
            fetch_redirect_response=False,
        )
        return commande

    def payer_mobile(self, commande, telephone="70123456"):
        return self.client.post(
            reverse("commande_paiement", args=[commande.reference]),
            {"moyen": "orange_money", "indicatif": "+223", "telephone": telephone},
        )

    def test_parcours_complet_mobile_money_ajoute_les_credits_une_fois(self):
        from django.core import mail

        commande = self.commander(2500)
        self.assertEqual(self.solde(), CREDITS_BIENVENUE)

        reponse = self.payer_mobile(commande, "70 12 34 56")
        self.assertRedirects(
            reponse, reverse("commande_confirmation", args=[commande.reference]),
            fetch_redirect_response=False,
        )
        commande.refresh_from_db()
        self.assertEqual(commande.statut, "en_attente")
        self.assertEqual(commande.detail_moyen, "+223 •• •• 34 56")
        self.assertEqual(self.solde(), CREDITS_BIENVENUE)  # rien avant le code

        page = self.client.get(reverse("commande_confirmation", args=[commande.reference]))
        self.assertContains(page, commande.code_confirmation)

        url_code = reverse("commande_confirmation", args=[commande.reference])
        reponse = self.client.post(url_code, {"code": commande.code_confirmation})
        self.assertRedirects(
            reponse, reverse("commande_recu", args=[commande.reference]),
            fetch_redirect_response=False,
        )
        self.assertEqual(self.solde(), CREDITS_BIENVENUE + 50)

        recu = self.client.get(reverse("commande_recu", args=[commande.reference]))
        self.assertContains(recu, "Paiement réussi")
        self.assertContains(recu, commande.reference)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(commande.reference, mail.outbox[0].subject)

        # Renvoyer le code (double clic, retour arrière) ne crédite pas deux fois.
        self.client.post(url_code, {"code": commande.code_confirmation})
        self.assertEqual(self.solde(), CREDITS_BIENVENUE + 50)

        historique = self.client.get(reverse("mes_credits"))
        self.assertContains(historique, "Recharge Orange Money (simulée)")

    def test_carte_de_test_passe_par_3d_secure(self):
        commande = self.commander(1000)
        reponse = self.client.post(
            reverse("commande_paiement", args=[commande.reference]),
            {
                "moyen": "carte",
                "titulaire": "Awa Diallo",
                "numero_carte": "4242 4242 4242 4242",
                "expiration": "12/39",
                "cvc": "123",
            },
        )
        commande.refresh_from_db()
        self.assertEqual(commande.detail_moyen, "Visa •••• 4242")
        page = self.client.get(reponse.url)
        self.assertContains(page, "3-D Secure")
        self.client.post(reponse.url, {"code": commande.code_confirmation})
        self.assertEqual(self.solde(), CREDITS_BIENVENUE + 20)

    def test_une_vraie_carte_est_refusee_en_mode_test(self):
        commande = self.commander(1000)
        reponse = self.client.post(
            reverse("commande_paiement", args=[commande.reference]),
            {
                "moyen": "carte",
                "titulaire": "Awa",
                "numero_carte": "5555 5555 5555 4444",
                "expiration": "12/39",
                "cvc": "123",
            },
        )
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "Ne saisis jamais une vraie carte")
        # Le numéro refusé n'est jamais renvoyé dans la page.
        self.assertNotContains(reponse, "5555 5555 5555 4444")
        commande.refresh_from_db()
        self.assertEqual(commande.statut, "creee")

    def test_solde_mobile_insuffisant_echoue_apres_le_code(self):
        commande = self.commander()
        self.payer_mobile(commande, "70120000")
        commande.refresh_from_db()
        reponse = self.client.post(
            reverse("commande_confirmation", args=[commande.reference]),
            {"code": commande.code_confirmation},
        )
        self.assertRedirects(
            reponse, reverse("commande_echec", args=[commande.reference]),
            fetch_redirect_response=False,
        )
        page = self.client.get(reponse.url)
        self.assertContains(page, "Solde mobile money insuffisant")
        self.assertEqual(self.solde(), CREDITS_BIENVENUE)

    def test_trois_codes_faux_bloquent_le_paiement(self):
        commande = self.commander()
        self.payer_mobile(commande)
        commande.refresh_from_db()
        faux = "111111" if commande.code_confirmation != "111111" else "222222"
        url = reverse("commande_confirmation", args=[commande.reference])
        reponse = self.client.post(url, {"code": faux})
        self.assertContains(reponse, "Il te reste 2 essais")
        self.client.post(url, {"code": faux})
        reponse = self.client.post(url, {"code": faux})
        self.assertRedirects(
            reponse, reverse("commande_echec", args=[commande.reference]),
            fetch_redirect_response=False,
        )
        self.assertEqual(self.solde(), CREDITS_BIENVENUE)

    def test_montant_invalide_ne_cree_pas_de_commande(self):
        from credits.models import CommandeCredits

        reponse = self.client.post(reverse("acheter_credits"), {"montant": "", "montant_libre": "1250"})
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "Le montant doit avancer par pas de 500 FCFA.")
        self.assertFalse(CommandeCredits.objects.exists())

    def test_montant_libre_sans_javascript(self):
        reponse = self.client.post(reverse("acheter_credits"), {"montant": "", "montant_libre": "7500"})
        from credits.models import CommandeCredits

        commande = CommandeCredits.objects.get(utilisateur=self.utilisateur)
        self.assertEqual((commande.montant_fcfa, commande.credits), (7500, 150))
        self.assertEqual(reponse.status_code, 302)

    def test_annulation_et_commande_d_un_autre_utilisateur(self):
        commande = self.commander()
        autre = Utilisateur.objects.create_user(
            username="intrus", email="intrus@example.com", password="motdepasse-de-test"
        )
        self.client.force_login(autre)
        self.assertEqual(
            self.client.get(reverse("commande_paiement", args=[commande.reference])).status_code,
            404,
        )
        self.client.force_login(self.utilisateur)
        self.client.post(reverse("commande_annuler", args=[commande.reference]))
        commande.refresh_from_db()
        self.assertEqual(commande.statut, "annulee")
        # Une commande annulée ne peut plus être payée.
        reponse = self.payer_mobile(commande)
        self.assertRedirects(
            reponse, reverse("commande_echec", args=[commande.reference]),
            fetch_redirect_response=False,
        )

    def test_commande_expiree(self):
        from datetime import timedelta

        from django.utils import timezone

        from credits.models import CommandeCredits

        commande = self.commander()
        CommandeCredits.objects.filter(pk=commande.pk).update(
            date_creation=timezone.now() - timedelta(hours=1)
        )
        reponse = self.payer_mobile(commande)
        commande.refresh_from_db()
        self.assertEqual(commande.statut, "expiree")
        self.assertEqual(reponse.status_code, 302)

    @override_settings(BETA_SIMULATED_PAYMENTS=False)
    def test_paiements_desactives(self):
        from credits.models import CommandeCredits

        reponse = self.client.post(reverse("acheter_credits"), {"montant": 1000})
        self.assertContains(reponse, "Recharge momentanément indisponible")
        self.assertFalse(CommandeCredits.objects.exists())


class PageTarifsTest(TestCase):
    def test_packs_et_calculateur(self):
        reponse = self.client.get(reverse("tarifs"), {"montant": 2500})
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(
            [(p["nom"], p["montant"], p["credits"]) for p in reponse.context["packs"]],
            [("Découverte", 1000, 20), ("Essentiel", 2500, 50), ("Pro", 5000, 100)],
        )
        self.assertEqual(reponse.context["resultat_calcul"]["audits_rapides"], 10)
        self.assertContains(reponse, "Le plus choisi")
        self.assertContains(reponse, f"{reverse('acheter_credits')}?montant=2500")

    def test_calculateur_erreur_en_francais(self):
        reponse = self.client.get(reverse("tarifs"), {"montant": 999})
        self.assertContains(reponse, "Le montant minimum est de 1000 FCFA.")
        self.assertIsNone(reponse.context["resultat_calcul"])

    def test_tarifs_suivent_le_prix_configure(self):
        with patch.object(credits_config, "PRIX_CREDIT_FCFA", 100):
            reponse = self.client.get(reverse("tarifs"))
        self.assertContains(reponse, "1 crédit = 100 FCFA")
        self.assertEqual(reponse.context["packs"][0]["credits"], 10)
