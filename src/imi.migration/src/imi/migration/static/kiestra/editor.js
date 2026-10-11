/* Initialize Kiestra employee selectors after Plone's Select2 becomes available. */
(function () {
  'use strict';
  // In the Plone toolbar, the first mouse press on a Select2 choice's X
  // can be consumed by focus/dropdown handlers. Remove that choice directly
  // on the first pointer press instead of relying on Select2's click handler.
  document.addEventListener('mousedown', function (event) {
    if (event.button !== 0) return;
    var target = event.target;
    var remove = target.closest && target.closest(
      '.kiestra-editor .select2-selection__choice__remove'
    );
    if (!remove) return;
    var choice = remove.closest('.select2-selection__choice');
    var container = remove.closest('.select2-container');
    var select = container && container.previousElementSibling;
    if (!choice || !select || !select.classList.contains('kiestra-staff-select')) return;
    var $ = window.jQuery;
    if (!$ || !$.fn || !$.fn.select2) return;

    var data = $(choice).data('data');
    if (!data && $.fn.select2.amd) {
      try {
        var utils = $.fn.select2.amd.require('select2/utils');
        data = utils.GetData(choice, 'data');
      } catch (error) { /* Older Select2 stores data on the jQuery node. */ }
    }
    if (!data || data.id == null) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    var id = String(data.id);
    Array.prototype.forEach.call(select.options, function (option) {
      if (option.value === id) option.selected = false;
    });
    $(select).trigger('change');
    // Suppress the subsequent click; the mousedown already removed the choice.
    remove.dataset.imiRemoved = '1';
  }, true);
  document.addEventListener('click', function (event) {
    var target = event.target;
    var remove = target.closest && target.closest(
      '.kiestra-editor .select2-selection__choice__remove'
    );
    if (remove && remove.dataset.imiRemoved === '1') {
      event.preventDefault();
      event.stopImmediatePropagation();
    }
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
