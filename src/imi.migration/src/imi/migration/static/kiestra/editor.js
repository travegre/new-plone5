/* Match the standard Dežurstva multi-person editor, retaining Kiestra cards. */
(function () {
  'use strict';
  function setup() {
    document.querySelectorAll('.kiestra-editor .kiestra-staff-select').forEach(function (select) {
      if (select.dataset.imiStaffReady) return;
      // Sort available employees alphabetically in the dropdown, irrespective of stored order.
      var options = Array.prototype.slice.call(select.options);
      options.sort(function (a, b) {
        return a.textContent.localeCompare(b.textContent, 'sl', { sensitivity: 'base' });
      });
      options.forEach(function (option) { select.appendChild(option); });
      var $ = window.jQuery;
      if ($ && $.fn && $.fn.select2) {
        $(select).select2({
          width: '100%',
          placeholder: 'Izberite osebe',
          allowClear: true,
          closeOnSelect: false,
          language: {
            noResults: function () { return 'Ni zadetkov'; },
            searching: function () { return 'Iskanje …'; }
          }
        });
        select.dataset.imiStaffReady = '1';
      } else {
        // Keep the native multiple-selection widget usable if Select2 is absent.
        select.classList.add('kiestra-native-select');
      }
    });
  }
  // Plone may load Select2 after DOMContentLoaded. Retry only until it is
  // available, with a bounded number of attempts and no DOM observer.
  var attempts = 0;
  function initializeWhenReady() {
    setup();
    var pending = document.querySelectorAll(
      '.kiestra-editor .kiestra-staff-select:not(.select2-hidden-accessible)'
    );
    if (pending.length && !(window.jQuery && window.jQuery.fn && window.jQuery.fn.select2)
        && attempts++ < 40) {
      window.setTimeout(initializeWhenReady, 150);
    }
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeWhenReady);
  } else {
    initializeWhenReady();
  }
  window.addEventListener('load', initializeWhenReady);
})();
