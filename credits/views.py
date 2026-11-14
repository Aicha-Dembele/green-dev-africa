from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_POST

from credits import config as credits_config
from credits.config import (
    COUT_PAGE_HORS_QUOTA,
    COUT_SITE_COMPLET_APPROFONDI,
    COUT_SITE_COMPLET_RAPIDE,
    CREDITS_BIENVENUE,
    QUOTA_GRATUIT_MENSUEL,
    TEXTE_OBTENIR_CREDITS,
)
from credits.forms import CodeConfirmationForm, MontantForm, PaiementForm
from credits.models import CommandeCredits, SoldeCredits
from credits.services import (
    annuler_commande,
    assurer_solde_utilisateur,
    compter_analyses_gratuites_du_mois,
    creer_commande,
    demander_confirmation,
    expirer_si_necessaire,
    marquer_echec,
    payer_commande,
)


def _libelle_transaction(transaction):
    if transaction.type == "achat_manuel":
        commande = getattr(transaction, "commande", None)
        if commande is not None:
            return f"Recharge {commande.nom_moyen} (simulée)"
        if transaction.note.startswith("Simulation gratuite de paiement"):
            return "Recharge simulée gratuite"

    libelles = {
        "bienvenue": "Crédits de bienvenue",
        "achat_manuel": "Achat manuel",
        "debit_analyse": "Débit pour une analyse",
        "remboursement": "Remboursement",
        "ajustement_admin": "Ajustement administratif",
    }
    return libelles.get(transaction.type, transaction.get_type_display())


def _detail_pack(montant):
    credits = credits_config.credits_pour_montant(montant)
    return {
        "montant": montant,
        "credits": credits,
        "audits_rapides": credits // COUT_SITE_COMPLET_RAPIDE,
        "audits_approfondis": credits // COUT_SITE_COMPLET_APPROFONDI,
        "audits_page": credits // COUT_PAGE_HORS_QUOTA,
    }


def _packs():
    return [{**pack, **_detail_pack(pack["montant"])} for pack in credits_config.PACKS]


def tarifs(request):
    couts_tarifs = [
        {
            "libelle": "Audit d'une page",
            "detail": f"Gratuit dans la limite de {QUOTA_GRATUIT_MENSUEL} par mois, puis",
            "credits": COUT_PAGE_HORS_QUOTA,
            "fcfa": credits_config.montant_pour_credits(COUT_PAGE_HORS_QUOTA),
        },
        {
            "libelle": "Site complet — rapide",
            "detail": "Jusqu'à 10 pages, mesures essentielles",
            "credits": COUT_SITE_COMPLET_RAPIDE,
            "fcfa": credits_config.montant_pour_credits(COUT_SITE_COMPLET_RAPIDE),
        },
        {
            "libelle": "Site complet — approfondi",
            "detail": "Jusqu'à 10 pages, toutes les règles",
            "credits": COUT_SITE_COMPLET_APPROFONDI,
            "fcfa": credits_config.montant_pour_credits(COUT_SITE_COMPLET_APPROFONDI),
        },
    ]
    montant_saisi = request.GET.get("montant", "")
    resultat_calcul = None
    erreur_calcul = ""
    if montant_saisi:
        try:
            montant = int(montant_saisi)
        except (TypeError, ValueError):
            erreur_calcul = "Saisis un montant entier en FCFA."
        else:
            try:
                resultat_calcul = _detail_pack(montant)
            except ValueError as erreur:
                erreur_calcul = str(erreur)

    return render(
        request,
        "credits/tarifs.html",
        {
            "packs": _packs(),
            "couts_tarifs": couts_tarifs,
            "moyens_paiement": credits_config.MOYENS_PAIEMENT,
            "prix_credit_fcfa": credits_config.PRIX_CREDIT_FCFA,
            "achat_minimum_fcfa": credits_config.ACHAT_MINIMUM_FCFA,
            "achat_pas_fcfa": credits_config.ACHAT_PAS_FCFA,
            "achat_maximum_fcfa": credits_config.ACHAT_MAXIMUM_FCFA,
            "montant_saisi": montant_saisi or "2500",
            "resultat_calcul": resultat_calcul,
            "erreur_calcul": erreur_calcul,
            "credits_bienvenue": CREDITS_BIENVENUE,
            "quota_gratuit_mensuel": QUOTA_GRATUIT_MENSUEL,
            "cout_rapide": COUT_SITE_COMPLET_RAPIDE,
            "cout_approfondi": COUT_SITE_COMPLET_APPROFONDI,
            "cout_page": COUT_PAGE_HORS_QUOTA,
            "texte_obtenir_credits": TEXTE_OBTENIR_CREDITS,
        },
    )


@login_required
def mes_credits(request):
    solde, _ = SoldeCredits.objects.get_or_create(utilisateur=request.user)
    solde.recalculer()
    transactions = list(
        request.user.credits_journal.select_related("commande").order_by("date", "pk")
    )
    historique = []
    solde_courant = 0
    credits_recus = 0
    depenses = 0
    for transaction in transactions:
        solde_courant += transaction.montant
        if transaction.montant > 0:
            credits_recus += transaction.montant
        else:
            depenses += abs(transaction.montant)
        historique.append(
            {
                "date": transaction.date,
                "libelle": _libelle_transaction(transaction),
                "montant": transaction.montant,
                "note": transaction.note,
                "solde_apres": solde_courant,
                "type": transaction.type,
                "est_positif": transaction.montant >= 0,
                "recu_url": (
                    reverse("commande_recu", args=[transaction.commande.reference])
                    if getattr(transaction, "commande", None)
                    else ""
                ),
            }
        )
    historique.reverse()

    gratuites_restantes = max(
        QUOTA_GRATUIT_MENSUEL - compter_analyses_gratuites_du_mois(request.user),
        0,
    )
    return render(
        request,
        "credits/mes_credits.html",
        {
            "solde": solde.solde,
            "gratuites_restantes": gratuites_restantes,
            "historique": historique,
            "credits_recus": credits_recus,
            "depenses": depenses,
            "dernier_mouvement": historique[0] if historique else None,
            "prix_credit_fcfa": credits_config.PRIX_CREDIT_FCFA,
            "montants_suggeres": credits_config.MONTANTS_SUGGERES,
            "texte_obtenir_credits": TEXTE_OBTENIR_CREDITS,
            "quota_gratuit_mensuel": QUOTA_GRATUIT_MENSUEL,
        },
    )


def _paiements_actifs():
    return getattr(settings, "BETA_SIMULATED_PAYMENTS", False)


def _commande_de(request, reference):
    """La commande de l'utilisateur connecté, à jour de son expiration."""
    commande = get_object_or_404(
        CommandeCredits, reference=reference, utilisateur=request.user
    )
    return expirer_si_necessaire(commande)


def _rediriger_selon_statut(commande):
    """Chaque étape n'est accessible que dans le bon état de la commande."""
    destinations = {
        CommandeCredits.Statut.CREEE: "commande_paiement",
        CommandeCredits.Statut.EN_ATTENTE: "commande_confirmation",
        CommandeCredits.Statut.PAYEE: "commande_recu",
    }
    return redirect(
        destinations.get(commande.statut, "commande_echec"), reference=commande.reference
    )


@login_required
def acheter_credits(request):
    """Étape 1 : choisir un pack ou un montant libre."""
    solde = assurer_solde_utilisateur(request.user)
    montant_initial = request.GET.get("montant", "")
    if request.method == "POST" and _paiements_actifs():
        # « Autre montant » : le bouton radio n'a pas de valeur sans JavaScript,
        # le montant est alors dans le champ libre.
        montant = request.POST.get("montant") or request.POST.get("montant_libre", "")
        formulaire = MontantForm({"montant": montant})
        if formulaire.is_valid():
            commande = creer_commande(request.user, formulaire.cleaned_data["montant"])
            return redirect("commande_paiement", reference=commande.reference)
        montant_initial = montant
    else:
        formulaire = MontantForm()

    packs = _packs()
    montants_packs = {str(pack["montant"]) for pack in packs}
    if not montant_initial:
        montant_initial = next(str(p["montant"]) for p in packs if p["populaire"])
    return render(
        request,
        "credits/acheter_credits.html",
        {
            "etape": 1,
            "solde": solde.solde,
            "packs": packs,
            "formulaire": formulaire,
            "montant_initial": montant_initial,
            "montant_libre": "" if montant_initial in montants_packs else montant_initial,
            "paiements_actifs": _paiements_actifs(),
            "prix_credit_fcfa": credits_config.PRIX_CREDIT_FCFA,
            "achat_minimum_fcfa": credits_config.ACHAT_MINIMUM_FCFA,
            "achat_pas_fcfa": credits_config.ACHAT_PAS_FCFA,
            "achat_maximum_fcfa": credits_config.ACHAT_MAXIMUM_FCFA,
            "cout_rapide": COUT_SITE_COMPLET_RAPIDE,
            "cout_approfondi": COUT_SITE_COMPLET_APPROFONDI,
        },
    )


@login_required
def commande_paiement(request, reference):
    """Étape 2 : choisir le moyen de paiement."""
    commande = _commande_de(request, reference)
    if commande.statut != CommandeCredits.Statut.CREEE:
        return _rediriger_selon_statut(commande)

    if request.method == "POST":
        formulaire = PaiementForm(request.POST)
        if formulaire.is_valid():
            demander_confirmation(
                commande, formulaire.cleaned_data["moyen"], formulaire.detail_moyen()
            )
            # Le refus éventuel (solde insuffisant, carte refusée) est connu
            # dès maintenant mais, comme chez un vrai opérateur, il n'est
            # annoncé qu'après la confirmation par code.
            refus = formulaire.sera_refuse()
            if refus:
                CommandeCredits.objects.filter(pk=commande.pk).update(motif_echec=refus)
            return redirect("commande_confirmation", reference=commande.reference)
    else:
        formulaire = PaiementForm(initial={"indicatif": "+223"})

    return render(
        request,
        "credits/commande_paiement.html",
        {
            "etape": 2,
            "commande": commande,
            "formulaire": formulaire,
            "moyens_paiement": credits_config.MOYENS_PAIEMENT,
            "indicatifs": credits_config.INDICATIFS,
            "moyen_choisi": formulaire["moyen"].value() or "orange_money",
            "carte_test": "4242 4242 4242 4242",
            "carte_test_refusee": "4000 0000 0000 0002",
            "suffixe_refuse": credits_config.SUFFIXE_TELEPHONE_REFUSE,
        },
    )


@login_required
def commande_confirmation(request, reference):
    """Étape 3 : saisir le code reçu par SMS ou le code 3-D Secure."""
    commande = _commande_de(request, reference)
    if commande.statut != CommandeCredits.Statut.EN_ATTENTE:
        return _rediriger_selon_statut(commande)

    formulaire = CodeConfirmationForm(request.POST or None)
    if request.method == "POST" and formulaire.is_valid():
        if formulaire.cleaned_data["code"] != commande.code_confirmation:
            commande.tentatives_code += 1
            commande.save(update_fields=["tentatives_code"])
            restantes = credits_config.TENTATIVES_CODE_MAX - commande.tentatives_code
            if restantes <= 0:
                marquer_echec(commande, "Trop de codes erronés : paiement bloqué par sécurité.")
                return redirect("commande_echec", reference=commande.reference)
            formulaire.add_error(
                "code",
                f"Code incorrect. Il te reste {restantes} essai{'s' if restantes > 1 else ''}.",
            )
        elif commande.motif_echec:
            marquer_echec(commande, commande.motif_echec)
            return redirect("commande_echec", reference=commande.reference)
        else:
            payer_commande(commande)
            _envoyer_recu(request, commande)
            return redirect("commande_recu", reference=commande.reference)

    return render(
        request,
        "credits/commande_confirmation.html",
        {"etape": 3, "commande": commande, "formulaire": formulaire},
    )


@login_required
def commande_recu(request, reference):
    """Étape 4 : le reçu de la commande payée."""
    commande = _commande_de(request, reference)
    if commande.statut != CommandeCredits.Statut.PAYEE:
        return _rediriger_selon_statut(commande)
    solde = assurer_solde_utilisateur(request.user)
    return render(
        request,
        "credits/commande_recu.html",
        {
            "etape": 4,
            "commande": commande,
            "solde": solde.solde,
            "audits_rapides": commande.credits // COUT_SITE_COMPLET_RAPIDE,
        },
    )


@login_required
def commande_echec(request, reference):
    """Paiement échoué, annulé ou expiré : on explique et on propose de réessayer."""
    commande = _commande_de(request, reference)
    if commande.est_ouverte or commande.statut == CommandeCredits.Statut.PAYEE:
        return _rediriger_selon_statut(commande)
    return render(request, "credits/commande_echec.html", {"commande": commande})


@login_required
@require_POST
def commande_annuler(request, reference):
    commande = _commande_de(request, reference)
    annuler_commande(commande)
    if commande.statut == CommandeCredits.Statut.ANNULEE:
        messages.info(request, f"Commande {commande.reference} annulée. Aucun crédit n'a été ajouté.")
        return redirect("acheter_credits")
    return _rediriger_selon_statut(commande)


def _envoyer_recu(request, commande):
    """Le reçu par e-mail, comme après un vrai paiement. Jamais bloquant."""
    if not request.user.email:
        return
    texte = render_to_string(
        "credits/email_recu.txt",
        {
            "commande": commande,
            "utilisateur": request.user,
            "lien": request.build_absolute_uri(
                reverse("commande_recu", args=[commande.reference])
            ),
        },
    )
    send_mail(
        f"Reçu de ta recharge {commande.reference}",
        texte,
        None,
        [request.user.email],
        fail_silently=True,
    )
