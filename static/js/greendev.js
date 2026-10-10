/* Green Dev Africa — le seul JavaScript du site.
 *
 * Il ajoute le petit œil qui montre ou cache le mot de passe. Rien d'autre :
 * environ 1 Ko, contre 90 Ko pour une bibliothèque qui ferait la même chose.
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
  });
})();
