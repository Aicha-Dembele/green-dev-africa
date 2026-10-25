/* Green Dev Africa — le seul JavaScript du site.
 *
 * Il ajoute le petit œil qui montre ou cache le mot de passe. Rien d'autre :
 * quelques Ko, contre des dizaines de Ko pour une bibliothèque qui ferait
 * la même chose.
 * Les pages restent utilisables si ce fichier ne charge pas — le champ reste
 * simplement masqué, comme avant.
 */
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
    var champs = document.querySelectorAll('input[type="password"]');
    for (var i = 0; i < champs.length; i++) {
      equiper(champs[i]);
    }

    document.querySelectorAll("[data-analyse-form]").forEach(function (form) {
      form.addEventListener("submit", function () {
        var bouton = form.querySelector("[data-analyse-submit]");
        var statut = form.querySelector("[data-analyse-chargement]");
        if (bouton && statut) {
          bouton.disabled = true;
          bouton.textContent = "Envoi de la demande…";
          statut.hidden = false;
          statut.textContent = "Enregistrement de ta demande d'analyse…";
          form.setAttribute("aria-busy", "true");
        }
      });
    });

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
          } else if (indexEtape === indexActuel) {
            icone.textContent = "→";
            etape.setAttribute("aria-current", "step");
          } else {
            icone.textContent = "○";
            etape.removeAttribute("aria-current");
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
              window.location.reload();
              return;
            }

            suivi.setAttribute("data-statut", donnees.statut);
            afficherEtapes(donnees.statut);
            if (donnees.statut === "en_attente") {
              titre.textContent = "Demande enregistrée — en attente";
              message.textContent =
                "Ta demande est bien enregistrée. L'analyse démarrera dès que le service la prendra en charge.";
            } else {
              titre.textContent = "Analyse en cours";
              message.textContent =
                "Le site est en cours de mesure. Les résultats apparaîtront ici automatiquement lorsqu'ils seront prêts.";
            }
            window.setTimeout(actualiserStatut, 2500);
          })
          .catch(function () {
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
        }
      });
    });
  });
})();
