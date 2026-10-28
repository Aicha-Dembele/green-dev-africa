from django.contrib.auth import get_user_model
from django.test import TestCase

from analyses.models import Analyse, ConfigurationAnalyse
from credits.config import (
    COUT_PAGE_HORS_QUOTA,
    CREDITS_BIENVENUE,
    QUOTA_GRATUIT_MENSUEL,
    TYPE_AUDIT_PAGE_UNIQUE,
)
from credits.models import JournalCredits, SoldeCredits
from credits.services import (
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

    def test_debit_normal(self):
        utilisateur = Utilisateur.objects.create_user(
            username="aicha",
            email="aicha@example.com",
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
