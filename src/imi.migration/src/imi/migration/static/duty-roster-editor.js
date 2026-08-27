/* Plone 5 editor behavior for imi.duty.roster_day.
 * Ports only the useful behavior from the legacy dezurstvo.js.
 * The old InAndOut filtering/layout is handled by Plone 5 Select2 + CSS.
 */
(function ($) {
  'use strict';

  function isDutyEditPage() {
    var body = document.body;
    return body &&
      body.classList.contains('portaltype-imi-duty-roster-day') &&
      body.classList.contains('template-edit');
  }

  function editingUrl(href) {
    if (!href || /\/edit(?:$|[?#])/.test(href)) {
      return href;
    }
    var hash = '';
    var query = '';
    var hashPos = href.indexOf('#');
    if (hashPos !== -1) {
      hash = href.substring(hashPos);
      href = href.substring(0, hashPos);
    }
    var queryPos = href.indexOf('?');
    if (queryPos !== -1) {
      query = href.substring(queryPos);
      href = href.substring(0, queryPos);
    }
    return href.replace(/\/$/, '') + '/edit' + query + hash;
  }

  function keepDayNavigationInEditMode() {
    $('a.next, a.previous').each(function () {
      var href = $(this).attr('href');
      if (href) {
        $(this).attr('href', editingUrl(href));
      }
    });
  }

  function preventAccidentalEnterSubmit() {
    $(document).on('keydown.imiDutyRoster', function (event) {
      if (!isDutyEditPage() || event.key !== 'Enter') {
        return;
      }

      var target = event.target;
      if (!target) {
        return;
      }

      // Select2 needs Enter to choose a filtered employee, and textareas
      // legitimately use Enter for line breaks.
      if ($(target).closest('.select2-container, .select2-dropdown').length ||
          target.tagName === 'TEXTAREA' ||
          target.tagName === 'BUTTON' ||
          target.type === 'submit') {
        return;
      }

      if (target.tagName === 'INPUT') {
        event.preventDefault();
      }
    });
  }

  $(function () {
    if (!isDutyEditPage()) {
      return;
    }
    keepDayNavigationInEditMode();
    preventAccidentalEnterSubmit();
  });
}(jQuery));
