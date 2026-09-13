(function () {
  'use strict';
  document.addEventListener('DOMContentLoaded', function () {
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
  });
}());
