(function () {
  'use strict';

  function setupExport(formId, periodId, personId, periodContainerId) {
    var form = document.getElementById(formId);
    if (!form) { return; }
    var period = document.getElementById(periodId);
    var person = personId ? document.getElementById(personId) : null;
    var periodContainer = periodContainerId ? document.getElementById(periodContainerId) : null;
    var range = form.querySelector('.date-range');
    var submit = form.querySelector('.submit');
    function refresh() {
      var personOK = !person || !!person.value;
      var mode = period ? period.value : '';
      if (periodContainer) { periodContainer.style.display = personOK ? 'block' : 'none'; }
      if (range) { range.style.display = (personOK && mode === 'oddo') ? 'inline-block' : 'none'; }
      if (submit) { submit.style.display = (personOK && !!mode) ? 'inline' : 'none'; }
    }
    if (period) { period.addEventListener('change', refresh); }
    if (person) { person.addEventListener('change', refresh); }
    refresh();
  }

  function setupStaffFilters() {
    document.querySelectorAll('.staff-filter[data-target]').forEach(function (input) {
      var select = document.getElementById(input.getAttribute('data-target'));
      if (!select) { return; }
      input.addEventListener('input', function () {
        var needle = input.value.toLowerCase();
        Array.prototype.forEach.call(select.options, function (option) {
          option.hidden = needle && option.text.toLowerCase().indexOf(needle) === -1 && !option.selected;
        });
      });
    });
  }

  function setupDirectoryDetails() {
    document.addEventListener('click', function (event) {
      var row = event.target.closest && event.target.closest('tr.tri[data-person]');
      if (!row) { return; }
      var detail = row.nextElementSibling;
      if (detail && detail.classList.contains('person-detail')) {
        detail.style.display = detail.style.display === 'table-row' ? 'none' : 'table-row';
      }
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    setupExport('nad-izvoz-1', 'nad-izvoz-1-izbira', null, null);
    setupExport('nad-izvoz-2', 'nad-izvoz-2-izbira', 'nad-izvoz-2-oseba', 'nad-obdobje');
    setupStaffFilters();
    setupDirectoryDetails();
  });
}());
