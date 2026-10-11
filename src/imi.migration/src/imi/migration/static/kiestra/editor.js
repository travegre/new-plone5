/* Initialize Kiestra employee selectors after Plone's Select2 becomes available. */
(function () {
  'use strict';
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
        closeOnSelect: false
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
