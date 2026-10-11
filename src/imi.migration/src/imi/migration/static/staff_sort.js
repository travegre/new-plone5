/* Consistent Slovenian alphabetical order for native public employee selectors. */
(function () {
  'use strict';
  function key(text) {
    return String(text || '').toLocaleLowerCase().replace(/č/g, 'c~')
      .replace(/š/g, 's~').replace(/ž/g, 'z~');
  }
  function sort(select) {
    var options = Array.prototype.slice.call(select.options);
    var empty = options.filter(function (option) { return option.value === ''; });
    var people = options.filter(function (option) { return option.value !== ''; });
    people.sort(function (a, b) {
      var x = key(a.text), y = key(b.text);
      return x < y ? -1 : (x > y ? 1 : 0);
    });
    empty.concat(people).forEach(function (option) { select.appendChild(option); });
  }
  function init() {
    Array.prototype.forEach.call(document.querySelectorAll('select.imi-staff-sorted'), sort);
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
}());
