/* Green Dev Africa — comportements légers, sans dépendance externe. */
(function () {
  "use strict";

  var OEIL_OUVERT =
    '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
    '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>';

  var OEIL_BARRE =
    '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
    '<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/>' +
    '<path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/>' +
    '<path d="M14.12 14.12a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>';

  function conteneurToasts() {
    var conteneur = document.querySelector("[data-toast-stack]");
    if (!conteneur) {
      conteneur = document.createElement("ul");
      conteneur.className = "messages toast-stack";
      conteneur.setAttribute("data-toast-stack", "");
      conteneur.setAttribute("aria-label", "Notifications récentes");
      document.body.appendChild(conteneur);
    }
    return conteneur;
  }

  function fermerToast(toast) {
    if (!toast) return;
    toast.classList.add("toast-sortant");
    window.setTimeout(function () { toast.remove(); }, 180);
  }

  function afficherToast(texte, type) {
    var toast = document.createElement("li");
    toast.className = type || "success";
    toast.setAttribute("role", type === "error" ? "alert" : "status");
    toast.setAttribute("aria-live", type === "error" ? "assertive" : "polite");
    toast.setAttribute("data-toast", "");

    var message = document.createElement("span");
    message.textContent = texte;
    var fermer = document.createElement("button");
    fermer.type = "button";
    fermer.className = "toast-fermer";
    fermer.setAttribute("aria-label", "Fermer la notification");
    fermer.textContent = "×";
    fermer.addEventListener("click", function () { fermerToast(toast); });
    toast.append(message, fermer);
    conteneurToasts().appendChild(toast);
    window.setTimeout(function () { fermerToast(toast); }, 5000);
    return toast;
  }

  function preparerToast(toast) {
    var bouton = document.createElement("button");
    bouton.type = "button";
    bouton.className = "toast-fermer";
    bouton.setAttribute("aria-label", "Fermer la notification");
    bouton.textContent = "×";
    bouton.addEventListener("click", function () { fermerToast(toast); });
    toast.appendChild(bouton);
    window.setTimeout(function () { fermerToast(toast); }, 5000);
  }

  function activerChargement(form, bouton) {
    if (bouton && bouton.name && bouton.value) {
      var champCache = document.createElement("input");
      champCache.type = "hidden";
      champCache.name = bouton.name;
      champCache.value = bouton.value;
      champCache.setAttribute("data-submit-preserve", "");
      form.appendChild(champCache);
    }

    form.dataset.submitting = "true";
    form.setAttribute("aria-busy", "true");
    var boutons = form.querySelectorAll('button[type="submit"], input[type="submit"]');
    boutons.forEach(function (element) {
      element.disabled = true;
      if (element === bouton && element.tagName === "BUTTON") {
        var libelle = element.dataset.loadingLabel || (element.textContent.trim() + "…");
        var spinner = document.createElement("span");
        spinner.className = "ui-spinner";
        spinner.setAttribute("aria-hidden", "true");
        var texte = document.createElement("span");
        texte.textContent = libelle;
        element.replaceChildren(spinner, texte);
      }
    });
  }

  function equiper(champ) {
    var enveloppe = document.createElement("div");
    enveloppe.className = "champ-mot-de-passe";
    champ.parentNode.insertBefore(enveloppe, champ);
    enveloppe.appendChild(champ);

    var bouton = document.createElement("button");
    bouton.type = "button"; // sinon le bouton enverrait le formulaire
    bouton.className = "oeil";
    bouton.innerHTML = OEIL_BARRE;
    bouton.setAttribute("aria-label", "Afficher le mot de passe");
    bouton.title = "Afficher le mot de passe";

    bouton.addEventListener("click", function () {
      var cache = champ.type === "password";
      champ.type = cache ? "text" : "password";
      bouton.innerHTML = cache ? OEIL_OUVERT : OEIL_BARRE;
      var intitule = cache ? "Masquer le mot de passe" : "Afficher le mot de passe";
      bouton.setAttribute("aria-label", intitule);
      bouton.title = intitule;
      champ.focus();
    });

    enveloppe.appendChild(bouton);
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-toast]").forEach(preparerToast);

    var confirmationDialog = document.querySelector("[data-confirm-dialog]");
    var pendingForm = null;
    var pendingSubmitter = null;
    var titreConfirmation = confirmationDialog && confirmationDialog.querySelector("[data-confirm-title]");
    var texteConfirmation = confirmationDialog && confirmationDialog.querySelector("[data-confirm-message]");
    var boutonConfirmation = confirmationDialog && confirmationDialog.querySelector("[data-confirm-accept]");

    if (confirmationDialog && boutonConfirmation) {
      confirmationDialog.querySelector("[data-confirm-cancel]").addEventListener("click", function () {
        confirmationDialog.close("cancel");
      });
      confirmationDialog.addEventListener("close", function () {
        if (pendingSubmitter && pendingSubmitter.isConnected) pendingSubmitter.focus();
        pendingForm = null;
        pendingSubmitter = null;
      });
      boutonConfirmation.addEventListener("click", function () {
        var form = pendingForm;
        var submitter = pendingSubmitter;
        if (!form) return;
        form.dataset.confirmed = "true";
        confirmationDialog.close("confirm");
        if (typeof form.requestSubmit === "function") {
          if (submitter) form.requestSubmit(submitter);
          else form.requestSubmit();
        } else {
          activerChargement(form, submitter);
          form.submit();
        }
      });
    }

    document.querySelectorAll('form[method="post"], form[data-loading]').forEach(function (form) {
      form.addEventListener("submit", function (event) {
        if (form.dataset.submitting === "true") {
          event.preventDefault();
          return;
        }

        var submitter = event.submitter || form.querySelector('button[type="submit"], input[type="submit"]');
        if (form.hasAttribute("data-confirm-message") && form.dataset.confirmed !== "true") {
          event.preventDefault();
          if (!confirmationDialog || typeof confirmationDialog.showModal !== "function") {
            if (!window.confirm(form.dataset.confirmMessage)) return;
          } else {
            pendingForm = form;
            pendingSubmitter = submitter;
            titreConfirmation.textContent = form.dataset.confirmTitle || "Confirmer cette action";
            texteConfirmation.textContent = form.dataset.confirmMessage;
            boutonConfirmation.textContent = form.dataset.confirmLabel || "Confirmer";
            confirmationDialog.showModal();
            boutonConfirmation.focus();
            return;
          }
          form.dataset.confirmed = "true";
          if (submitter) form.requestSubmit(submitter);
          else form.requestSubmit();
          return;
        }

        activerChargement(form, submitter);
      });
    });

    var champs = document.querySelectorAll('input[type="password"]');
    for (var i = 0; i < champs.length; i++) {
      equiper(champs[i]);
    }

    document.querySelectorAll("[data-analyse-form]").forEach(function (form) {
      form.addEventListener("submit", function () {
        var bouton = form.querySelector("[data-analyse-submit]");
        var statut = form.querySelector("[data-analyse-chargement]");
        var carteCout = document.querySelector("[data-cout-analyse]");
        if (bouton && statut) {
          statut.hidden = false;
          statut.textContent = "Enregistrement de ta demande d'analyse…";
          form.setAttribute("aria-busy", "true");
        }
        if (carteCout) {
          carteCout.classList.add("is-loading");
        }
      });
    });

    var cartes = document.querySelectorAll("[data-reveal]");
    cartes.forEach(function (carte, index) {
      carte.style.transitionDelay = (index * 120) + "ms";
    });

    if ("IntersectionObserver" in window) {
      var observer = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            observer.unobserve(entry.target);
          }
        });
      }, { threshold: 0.2 });

      cartes.forEach(function (carte) {
        observer.observe(carte);
      });
    } else {
      cartes.forEach(function (carte) {
        carte.classList.add("is-visible");
      });
    }

    var loader = document.querySelector(".accueil-loader");
    if (loader) {
      window.setTimeout(function () {
        loader.style.opacity = "0.7";
      }, 450);
    }

    var carteCout = document.querySelector("[data-cout-analyse]");
    if (carteCout) {
      var typeAudit = document.getElementById("id_type_audit");
      var modeAnalyse = document.getElementById("id_mode_analyse");

      function nombre(valeur) {
        var nombreVal = Number(valeur);
        return Number.isFinite(nombreVal) ? nombreVal : 0;
      }

      function mettreAJourCout() {
        var solde = nombre(carteCout.dataset.solde);
        var restantes = nombre(carteCout.dataset.gratuites);
        var coutPage = nombre(carteCout.dataset.coutPage);
        var coutSiteRapide = nombre(carteCout.dataset.coutSiteRapide);
        var coutSiteApprofondi = nombre(carteCout.dataset.coutSiteApprofondi);
        var valeurType = typeAudit ? typeAudit.value : "page_unique";
        var valeurMode = modeAnalyse ? modeAnalyse.value : "rapide";
        var cout = 0;

        if (valeurType === "page_unique") {
          cout = restantes > 0 ? 0 : coutPage;
        } else if (valeurType === "site_complet") {
          cout = valeurMode === "approfondi" ? coutSiteApprofondi : coutSiteRapide;
        }

        var message = document.querySelector("[data-analyse-cout-message]");
        var erreur = document.querySelector("[data-analyse-solde-insuffisant]");

        if (message) {
          if (cout === 0) {
            message.textContent = "Gratuite : il vous reste " + restantes + " analyse" + (restantes === 1 ? "" : "s") + " gratuite" + (restantes === 1 ? "" : "s") + " ce mois-ci.";
          } else {
            message.textContent = "Cette analyse coûte " + cout + " crédit" + (cout === 1 ? "" : "s") + ". Il vous en reste " + solde + " crédit" + (solde === 1 ? "" : "s") + ".";
          }
        }

        var bouton = document.querySelector("[data-analyse-submit]");
        if (bouton) {
          bouton.disabled = (cout > 0 && solde < cout) || (document.querySelector("[data-analyse-form]") && document.querySelector("[data-analyse-form]").getAttribute("aria-busy") === "true");
        }

        if (erreur) {
          erreur.hidden = cout === 0 || solde >= cout;
        }
      }

      [typeAudit, modeAnalyse].forEach(function (champ) {
        if (champ) {
          champ.addEventListener("change", mettreAJourCout);
        }
      });
      mettreAJourCout();
    }

    var suivi = document.querySelector("[data-analyse-suivi]");
    if (suivi) {
      var titre = suivi.querySelector("[data-analyse-titre]");
      var message = suivi.querySelector("[data-analyse-message]");
      var etapes = suivi.querySelectorAll("[data-etape]");
      var urlStatut = suivi.getAttribute("data-url");

      function afficherEtapes(statut) {
        var ordre = ["en_attente", "en_cours", "terminee"];
        var indexActuel = ordre.indexOf(statut);

        etapes.forEach(function (etape) {
          var indexEtape = ordre.indexOf(etape.getAttribute("data-etape"));
          var icone = etape.querySelector("[data-icone]");
          if (indexEtape < indexActuel) {
            icone.textContent = "✓";
            etape.removeAttribute("aria-current");
            etape.classList.add("est-terminee");
          } else if (indexEtape === indexActuel) {
            icone.textContent = "→";
            etape.setAttribute("aria-current", "step");
            etape.classList.remove("est-terminee");
          } else {
            icone.textContent = "○";
            etape.removeAttribute("aria-current");
            etape.classList.remove("est-terminee");
          }
        });
      }

      function actualiserStatut() {
        window.fetch(urlStatut, {
          headers: { Accept: "application/json" },
          credentials: "same-origin"
        })
          .then(function (reponse) {
            if (!reponse.ok) {
              throw new Error("Le statut n'est pas disponible.");
            }
            return reponse.json();
          })
          .then(function (donnees) {
            if (donnees.statut === "terminee" || donnees.statut === "echouee") {
              suivi.setAttribute("data-statut", donnees.statut);
              suivi.setAttribute("aria-busy", "false");
              window.location.reload();
              return;
            }

            suivi.setAttribute("data-statut", donnees.statut);
            suivi.setAttribute("aria-busy", "true");
            suivi.classList.remove("etat-analyse-attente", "etat-analyse-en-cours", "etat-analyse-terminee");
            if (donnees.statut === "en_attente") {
              suivi.classList.add("etat-analyse-attente");
              titre.textContent = "Demande enregistrée — en attente";
            } else {
              suivi.classList.add("etat-analyse-en-cours");
              titre.textContent = "Analyse en cours";
            }
            afficherEtapes(donnees.statut);
            message.textContent = donnees.message ||
              (donnees.statut === "en_attente"
                ? "Ta demande est bien enregistrée. L'analyse démarrera dès que le service la prendra en charge."
                : "Le site est en cours de mesure. Les résultats apparaîtront ici automatiquement lorsqu'ils seront prêts.");
            window.setTimeout(actualiserStatut, 2500);
          })
          .catch(function () {
            suivi.classList.add("etat-analyse-attente");
            message.textContent =
              "Le suivi est momentanément indisponible. Ta demande reste enregistrée ; nouvelle vérification dans quelques instants.";
            window.setTimeout(actualiserStatut, 5000);
          });
      }

      window.setTimeout(actualiserStatut, 1500);
    }

    document.querySelectorAll("[data-copier-lien]").forEach(function (bouton) {
      bouton.addEventListener("click", async function () {
        var ligne = bouton.closest("tr");
        var lien = ligne && ligne.querySelector(".partage-lien");
        var statut = document.querySelector("[data-copie-statut]");
        if (!lien || !statut) {
          return;
        }

        try {
          await navigator.clipboard.writeText(lien.href);
          statut.textContent = "Lien copié dans le presse-papiers.";
          afficherToast("Lien de partage copié.", "success");
        } catch {
          lien.focus();
          var selection = window.getSelection();
          if (selection) {
            var plage = document.createRange();
            plage.selectNodeContents(lien);
            selection.removeAllRanges();
            selection.addRange(plage);
          }
          statut.textContent = "Copie automatique indisponible. Le lien est sélectionné : copie-le manuellement.";
          afficherToast("Copie automatique indisponible. Le lien est sélectionné pour une copie manuelle.", "error");
        }
      });
    });
  });
})();

/* --- Tarifs et parcours d'achat de crédits ---
 * Tout fonctionne sans JavaScript (formulaires classiques) ; ce bloc ajoute
 * le calcul en direct, l'affichage des champs du moyen choisi et l'écran de
 * traitement du paiement. */
(function () {
  "use strict";

  function milliers(n) {
    return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, " ");
  }

  function verifierMontant(montant, min, max, pas) {
    if (!montant && montant !== 0) return "Saisis un montant entier en FCFA.";
    if (montant < min) return "Le montant minimum est de " + milliers(min) + " FCFA.";
    if (montant > max) return "Le montant maximum est de " + milliers(max) + " FCFA.";
    if ((montant - min) % pas !== 0) return "Le montant doit avancer par pas de " + pas + " FCFA.";
    return "";
  }

  function calculateurTarifs(bloc) {
    var prix = Number(bloc.dataset.prix);
    var rapide = Number(bloc.dataset.rapide);
    var approfondi = Number(bloc.dataset.approfondi);
    var curseur = bloc.querySelector("[data-calcul-curseur]");
    var champ = bloc.querySelector("[data-calcul-montant]");
    var erreur = bloc.querySelector("[data-calcul-erreur]");
    var chiffres = bloc.querySelector("[data-calcul-chiffres]");
    var lien = bloc.querySelector("[data-calcul-lien]");
    var bouton = bloc.querySelector("[data-calcul-bouton]");
    var min = Number(champ.min), max = Number(champ.max), pas = Number(champ.step);

    curseur.hidden = false;
    if (bouton) bouton.hidden = true;

    function mettreAJour(source) {
      var montant = parseInt(source.value, 10);
      if (source === curseur) champ.value = montant;
      else if (!isNaN(montant)) curseur.value = montant;
      var message = verifierMontant(montant, min, max, pas);
      erreur.hidden = !message;
      erreur.textContent = message;
      chiffres.hidden = Boolean(message);
      lien.setAttribute("aria-disabled", message ? "true" : "false");
      lien.classList.toggle("bouton-desactive", Boolean(message));
      if (message) return;
      var credits = Math.floor(montant / prix);
      bloc.querySelector("[data-calcul-credits]").textContent = credits;
      bloc.querySelector("[data-calcul-rapides]").textContent = Math.floor(credits / rapide);
      bloc.querySelector("[data-calcul-approfondis]").textContent = Math.floor(credits / approfondi);
      lien.href = lien.href.split("?")[0] + "?montant=" + montant;
    }

    curseur.addEventListener("input", function () { mettreAJour(curseur); });
    champ.addEventListener("input", function () { mettreAJour(champ); });
    lien.addEventListener("click", function (event) {
      if (lien.getAttribute("aria-disabled") === "true") event.preventDefault();
    });
    mettreAJour(champ);
  }

  function choixMontant(form) {
    var prix = Number(form.dataset.prix);
    var rapide = Number(form.dataset.rapide);
    var min = Number(form.dataset.min), max = Number(form.dataset.max), pas = Number(form.dataset.pas);
    var radios = form.querySelectorAll('input[name="montant"]');
    var radioLibre = form.querySelector("[data-montant-libre-choix]");
    var champLibre = form.querySelector("[data-montant-libre]");
    var bouton = form.querySelector('button[type="submit"]');
    var desactiveServeur = bouton.disabled;

    function afficher(id, texte) { form.querySelector("[data-resume-" + id + "]").textContent = texte; }

    function mettreAJour() {
      radioLibre.value = champLibre.value;
      var choisi = form.querySelector('input[name="montant"]:checked');
      var montant = choisi ? parseInt(choisi.value, 10) : NaN;
      var message = choisi === radioLibre ? verifierMontant(montant, min, max, pas) : (choisi ? "" : "Choisis un montant.");
      if (message) {
        ["montant", "credits", "total"].forEach(function (id) { afficher(id, "—"); });
        afficher("usage", choisi === radioLibre && champLibre.value ? message : "");
        bouton.disabled = true;
        return;
      }
      var credits = Math.floor(montant / prix);
      afficher("montant", milliers(montant) + " FCFA");
      afficher("credits", "+" + credits);
      afficher("total", milliers(montant) + " FCFA");
      afficher("usage", "≈ " + Math.floor(credits / rapide) + " audits de site complet rapides.");
      bouton.disabled = desactiveServeur;
    }

    radios.forEach(function (radio) { radio.addEventListener("change", mettreAJour); });
    champLibre.addEventListener("focus", function () { radioLibre.checked = true; mettreAJour(); });
    champLibre.addEventListener("input", function () { radioLibre.checked = true; mettreAJour(); });
    mettreAJour();
  }

  function formulairePaiement(form) {
    var radios = form.querySelectorAll('input[name="moyen"]');
    var blocs = form.querySelectorAll("[data-details]");

    function afficherDetails() {
      var choisi = form.querySelector('input[name="moyen"]:checked');
      var famille = choisi ? choisi.dataset.famille : "";
      blocs.forEach(function (bloc) { bloc.hidden = bloc.dataset.details !== famille; });
    }
    radios.forEach(function (radio) { radio.addEventListener("change", afficherDetails); });
    afficherDetails();

    var carte = form.querySelector("[data-numero-carte]");
    if (carte) {
      carte.addEventListener("input", function () {
        var chiffres = carte.value.replace(/\D/g, "").slice(0, 19);
        carte.value = chiffres.replace(/(\d{4})(?=\d)/g, "$1 ");
      });
    }
    var expiration = form.querySelector("[data-expiration]");
    if (expiration) {
      expiration.addEventListener("input", function (event) {
        var chiffres = expiration.value.replace(/\D/g, "").slice(0, 4);
        if (chiffres.length > 2 || (chiffres.length === 2 && event.inputType !== "deleteContentBackward")) {
          chiffres = chiffres.slice(0, 2) + "/" + chiffres.slice(2);
        }
        expiration.value = chiffres;
      });
    }
  }

  function ecranTraitement(form) {
    var voile = document.querySelector("[data-traitement-voile]");
    if (!voile) return;
    form.addEventListener("submit", function (event) {
      if (form.dataset.traitementEnvoye === "true" || event.defaultPrevented) return;
      event.preventDefault();
      voile.querySelector("[data-traitement-message]").textContent =
        form.dataset.traitementTexte || "Traitement du paiement…";
      voile.hidden = false;
      form.dataset.traitementEnvoye = "true";
      // Le délai imite l'aller-retour avec l'opérateur.
      window.setTimeout(function () { HTMLFormElement.prototype.submit.call(form); }, 1600);
    });
  }

  function compteARebours(element) {
    var fin = new Date(element.dataset.compteARebours).getTime();
    if (isNaN(fin)) return;
    function afficher() {
      var reste = Math.max(0, Math.round((fin - Date.now()) / 1000));
      var minutes = Math.floor(reste / 60), secondes = reste % 60;
      element.textContent = reste
        ? "Cette demande expire dans " + minutes + " min " + (secondes < 10 ? "0" : "") + secondes + " s."
        : "Cette demande a expiré : recharge la page.";
      if (reste) window.setTimeout(afficher, 1000);
    }
    afficher();
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-calculateur]").forEach(calculateurTarifs);
    document.querySelectorAll("[data-achat-montant]").forEach(choixMontant);
    document.querySelectorAll("[data-paiement]").forEach(formulairePaiement);
    document.querySelectorAll("form[data-traitement]").forEach(ecranTraitement);
    document.querySelectorAll("[data-compte-a-rebours]").forEach(compteARebours);
    document.querySelectorAll("[data-imprimer]").forEach(function (bouton) {
      bouton.addEventListener("click", function () { window.print(); });
    });
  });
})();
