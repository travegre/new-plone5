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
        select.dataset.imiStaffReady = '1';
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
      } else {
        // Keep the native multiple-selection widget usable if Select2 is absent.
        select.classList.add('kiestra-native-select');
      }
    });
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setup);
  } else {
    setup();
  }
  window.addEventListener('load', setup);
  // Plone can inject editor markup without a document reload. Scripts inside
  // injected fragments are not guaranteed to execute, so initialize new cards
  // whenever the content region is replaced.
  function watch() {
    if (!window.MutationObserver || !document.body) return;
    var observer = new MutationObserver(function (mutations) {
      for (var i = 0; i < mutations.length; i++) {
        if (mutations[i].addedNodes.length) {
          setup();
          break;
        }
      }
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', watch);
  } else {
    watch();
  }
})();
