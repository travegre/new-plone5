(function () {
  'use strict';

  function isoToSlovenian(value) {
    if (!value) { return ''; }
    var parts = value.split('-');
    if (parts.length !== 3) { return value; }
    return parts[2] + '.' + parts[1] + '.' + parts[0];
  }

  function updateExportForm(formId, periodId, personId) {
    var form = document.getElementById(formId);
    if (!form) { return; }
    var period = document.getElementById(periodId);
    var person = personId ? document.getElementById(personId) : null;
    var range = form.querySelector('.date-range');
    var submit = form.querySelector('.submit');
    var periodContainer = person ? form.querySelector('#obdobje') : null;
    var fromWidget = form.querySelector('input[data-export-date="od"]');
    var toWidget = form.querySelector('input[data-export-date="do"]');
    var fromValue = form.querySelector('input[type="hidden"][name="od"]');
    var toValue = form.querySelector('input[type="hidden"][name="do"]');

    function refresh() {
      var mode = period ? period.value : '';
      var personOk = !person || !!person.value;
      if (periodContainer) {
        periodContainer.style.display = personOk ? 'block' : 'none';
      }
      if (range) {
        range.style.display = (mode === 'oddo' && personOk) ? 'inline-block' : 'none';
      }
      if (submit) {
        submit.style.display = (mode && personOk) ? 'inline' : 'none';
      }
    }

    function syncDates() {
      if (fromWidget && fromValue) { fromValue.value = isoToSlovenian(fromWidget.value); }
      if (toWidget && toValue) { toValue.value = isoToSlovenian(toWidget.value); }
    }

    if (period) { period.addEventListener('change', refresh); }
    if (person) { person.addEventListener('change', refresh); }
    if (fromWidget) { fromWidget.addEventListener('change', syncDates); }
    if (toWidget) { toWidget.addEventListener('change', syncDates); }
    form.addEventListener('submit', syncDates);
    refresh();
  }

  document.addEventListener('DOMContentLoaded', function () {
    updateExportForm('izvoz-1', 'izvoz-1-izbira', null);
    updateExportForm('izvoz-2', 'izvoz-2-izbira', 'izvoz-2-oseba');
  });
}());
