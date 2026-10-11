/* Initialize Kiestra employee selectors after Plone's Select2 becomes available. */
(function () {
  'use strict';
  // Plone ships Select2 3.x, whose multi-choice remove button is an <a>
  // inside .select2-search-choice (not Select2 4's choice__remove).
  // Remove the corresponding selected option on the first mouse press.
  document.addEventListener('mousedown', function (event) {
    if (event.button !== 0) return;
    var target = event.target;
    var remove = target.closest && target.closest(
      '.kiestra-editor .select2-search-choice-close'
    );
    if (!remove) return;
    var choice = remove.closest('.select2-search-choice');
    var container = remove.closest('.select2-container-multi');
    var select = container && container.nextElementSibling;
    if (!choice || !select || select.tagName !== 'SELECT' ||
        !select.classList.contains('kiestra-staff-select')) return;
    var $ = window.jQuery;
    if (!$ || !$.fn || !$.fn.select2) return;

    // Select2 3.x stores its choice data with jQuery.
    var data = $(choice).data('select2-data') || $(choice).data('data');
    var id = data && data.id != null ? String(data.id) : null;
    if (id === null) {
      // Fallback for versions which keep the choice data privately:
      // match the visible employee label to its option.
      var label = choice.querySelector('div');
      var name = label && label.textContent.trim();
      Array.prototype.some.call(select.options, function (option) {
        if (option.selected && option.textContent.trim() === name) {
          id = option.value;
          return true;
        }
        return false;
      });
    }
    if (id === null) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    Array.prototype.forEach.call(select.options, function (option) {
      if (option.value === id) option.selected = false;
    });
    $(select).trigger('change');
  }, true);

  var attempts = 0;
  var timer = null;

  function setup() {
    var selects = document.querySelectorAll('.kiestra-editor .kiestra-staff-select');
    if (!selects.length) return true;

    var $ = window.jQuery;
    if (!$ || !$.fn || typeof $.fn.select2 !== 'function') return false;

    for (var i = 0; i < selects.length; i++) {
      var select = selects[i];
      if (select.dataset.imiStaffReady === '1' ||
          select.classList.contains('select2-hidden-accessible')) continue;

      // The server already supplies alphabetically sorted employee options.
      // Reordering DOM options on each attempt caused an initialization error.
      $(select).select2({
        width: '100%',
        placeholder: 'Izberite osebe',
        allowClear: true,
        closeOnSelect: true
      });
      select.dataset.imiStaffReady = '1';
      select.classList.remove('kiestra-native-select');
    }
    return true;
  }

  function initializeWhenReady() {
    if (timer !== null) {
      window.clearTimeout(timer);
      timer = null;
    }
    if (!setup() && attempts++ < 40) {
      timer = window.setTimeout(initializeWhenReady, 150);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeWhenReady);
  } else {
    initializeWhenReady();
  }
  window.addEventListener('load', initializeWhenReady);
})();
