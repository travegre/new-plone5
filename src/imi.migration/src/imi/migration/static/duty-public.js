(function () {
  'use strict';

  function updateExportForm(formId, periodId, personId) {
    var form = document.getElementById(formId);
    if (!form) { return; }
    var period = document.getElementById(periodId);
    var person = personId ? document.getElementById(personId) : null;
    var range = form.querySelector('.date-range');
    var submit = form.querySelector('.submit');
    var periodContainer = person ? form.querySelector('#obdobje') : null;

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

    if (period) { period.addEventListener('change', refresh); }
    if (person) { person.addEventListener('change', refresh); }
    refresh();
  }

  document.addEventListener('DOMContentLoaded', function () {
    updateExportForm('izvoz-1', 'izvoz-1-izbira', null);
    updateExportForm('izvoz-2', 'izvoz-2-izbira', 'izvoz-2-oseba');
  });
}());
