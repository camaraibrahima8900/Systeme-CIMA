/**
 * searchable-select.js
 * Transforme automatiquement tout <select> ayant 8 options ou plus
 * en un champ avec recherche/filtre au-dessus.
 * Aucune dépendance externe. S'applique à tous les formulaires de l'appli.
 *
 * Utilisation : inclure ce fichier une seule fois (dans base.html par exemple).
 * Rien à changer dans les templates existants : le script détecte
 * automatiquement tous les <select> de la page au chargement.
 */
(function () {
  "use strict";

  var SEUIL_OPTIONS = 2; // temporairement abaissé pour tester (remettre à 8 avant la prod)

  function enrichirSelect(select) {
    if (select.dataset.searchEnhanced === "1") return;
    if (select.options.length < SEUIL_OPTIONS) return;

    select.dataset.searchEnhanced = "1";

    // Conteneur wrapper
    var wrapper = document.createElement("div");
    wrapper.className = "searchable-select-wrapper";
    select.parentNode.insertBefore(wrapper, select);

    // Champ de recherche
    var input = document.createElement("input");
    input.type = "text";
    input.className = "searchable-select-input";
    input.placeholder = "Rechercher...";
    input.autocomplete = "off";

    // Liste déroulante des résultats
    var liste = document.createElement("div");
    liste.className = "searchable-select-liste";
    liste.style.display = "none";

    wrapper.appendChild(input);
    wrapper.appendChild(liste);
    wrapper.appendChild(select);
    select.style.display = "none";

    // Construire les options internes à partir du <select> réel
    var options = Array.prototype.map.call(select.options, function (opt) {
      return { value: opt.value, label: opt.textContent, disabled: opt.disabled };
    });

    function afficherSelection() {
      var opt = select.options[select.selectedIndex];
      input.value = opt && opt.value ? opt.textContent : "";
    }

    function construireListe(filtre) {
      liste.innerHTML = "";
      var f = (filtre || "").toLowerCase();
      var resultats = options.filter(function (o) {
        return !o.disabled && o.label.toLowerCase().indexOf(f) !== -1;
      });

      if (resultats.length === 0) {
        var vide = document.createElement("div");
        vide.className = "searchable-select-item searchable-select-item--vide";
        vide.textContent = "Aucun résultat";
        liste.appendChild(vide);
        return;
      }

      resultats.forEach(function (o) {
        var item = document.createElement("div");
        item.className = "searchable-select-item";
        item.textContent = o.label;
        item.dataset.value = o.value;
        item.addEventListener("mousedown", function (e) {
          e.preventDefault();
          select.value = o.value;
          select.dispatchEvent(new Event("change", { bubbles: true }));
          afficherSelection();
          liste.style.display = "none";
        });
        liste.appendChild(item);
      });
    }

    input.addEventListener("focus", function () {
      construireListe(input.value === (select.options[select.selectedIndex] || {}).textContent ? "" : input.value);
      liste.style.display = "block";
    });

    input.addEventListener("input", function () {
      construireListe(input.value);
      liste.style.display = "block";
    });

    input.addEventListener("blur", function () {
      // Laisse le temps au mousedown de l'item de se déclencher avant de fermer
      setTimeout(function () {
        liste.style.display = "none";
        afficherSelection();
      }, 150);
    });

    afficherSelection();
  }

  function initSearchableSelects(racine) {
    var scope = racine || document;
    var selects = scope.querySelectorAll("select");
    selects.forEach(enrichirSelect);
  }

  document.addEventListener("DOMContentLoaded", function () {
    initSearchableSelects();
  });

  // Expose pour ré-application manuelle après un ajout dynamique de <select> (ex: contenu chargé en AJAX)
  window.initSearchableSelects = initSearchableSelects;
})();
