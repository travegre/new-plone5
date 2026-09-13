(function () {
  'use strict';

  var MONTHS = ['januar', 'februar', 'marec', 'april', 'maj', 'junij',
                'julij', 'avgust', 'september', 'oktober', 'november', 'december'];
  var DAYS = ['Po', 'To', 'Sr', 'Če', 'Pe', 'So', 'Ne'];

  function pad(value) { return value < 10 ? '0' + value : String(value); }

  function formatDate(date) {
    return pad(date.getDate()) + '.' + pad(date.getMonth() + 1) + '.' + date.getFullYear();
  }

  function parseDate(value) {
    var match = String(value || '').trim().match(/^(\d{1,2})\.(\d{1,2})\.(\d{4})$/);
    if (!match) {
      match = String(value || '').trim().match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);
      if (!match) { return null; }
      match = [match[0], match[3], match[2], match[1]];
    }
    var day = Number(match[1]);
    var month = Number(match[2]) - 1;
    var year = Number(match[3]);
    var date = new Date(year, month, day);
    return date.getFullYear() === year && date.getMonth() === month && date.getDate() === day ? date : null;
  }

  function init(input) {
    if (input.dataset.slDatePickerReady) { return; }
    input.dataset.slDatePickerReady = '1';
    input.type = 'text';
    input.setAttribute('inputmode', 'numeric');
    input.setAttribute('placeholder', 'dd.mm.llll');
    input.setAttribute('autocomplete', 'off');

    var initial = parseDate(input.value);
    if (initial) { input.value = formatDate(initial); }

    var wrapper = document.createElement('span');
    wrapper.className = 'sl-date-picker-wrap';
    input.parentNode.insertBefore(wrapper, input);
    wrapper.appendChild(input);

    var button = document.createElement('button');
    button.type = 'button';
    button.className = 'sl-date-picker-button';
    button.setAttribute('aria-label', 'Izberi datum');
    button.textContent = '▣';
    wrapper.appendChild(button);

    var popup = document.createElement('div');
    popup.className = 'sl-date-picker-popup';
    popup.hidden = true;
    wrapper.appendChild(popup);

    var shown = initial || new Date();
    shown = new Date(shown.getFullYear(), shown.getMonth(), 1);

    function close() { popup.hidden = true; }

    function choose(date) {
      input.value = formatDate(date);
      input.dispatchEvent(new Event('change', {bubbles: true}));
      close();
      input.focus();
    }

    function render() {
      popup.innerHTML = '';
      var header = document.createElement('div');
      header.className = 'sl-date-picker-header';
      var prev = document.createElement('button');
      prev.type = 'button'; prev.textContent = '‹'; prev.setAttribute('aria-label', 'Prejšnji mesec');
      var title = document.createElement('strong');
      title.textContent = MONTHS[shown.getMonth()] + ' ' + shown.getFullYear();
      var next = document.createElement('button');
      next.type = 'button'; next.textContent = '›'; next.setAttribute('aria-label', 'Naslednji mesec');
      header.appendChild(prev); header.appendChild(title); header.appendChild(next);
      popup.appendChild(header);

      prev.addEventListener('click', function () { shown.setMonth(shown.getMonth() - 1); render(); });
      next.addEventListener('click', function () { shown.setMonth(shown.getMonth() + 1); render(); });

      var grid = document.createElement('div');
      grid.className = 'sl-date-picker-grid';
      DAYS.forEach(function (name) {
        var label = document.createElement('span');
        label.className = 'sl-date-picker-weekday';
        label.textContent = name;
        grid.appendChild(label);
      });

      var first = new Date(shown.getFullYear(), shown.getMonth(), 1);
      var offset = (first.getDay() + 6) % 7;
      var days = new Date(shown.getFullYear(), shown.getMonth() + 1, 0).getDate();
      var i;
      for (i = 0; i < offset; i += 1) {
        grid.appendChild(document.createElement('span'));
      }
      for (i = 1; i <= days; i += 1) {
        (function (day) {
          var cell = document.createElement('button');
          cell.type = 'button';
          cell.textContent = String(day);
          cell.addEventListener('click', function () {
            choose(new Date(shown.getFullYear(), shown.getMonth(), day));
          });
          grid.appendChild(cell);
        }(i));
      }
      popup.appendChild(grid);

      var today = document.createElement('button');
      today.type = 'button';
      today.className = 'sl-date-picker-today';
      today.textContent = 'Danes';
      today.addEventListener('click', function () { choose(new Date()); });
      popup.appendChild(today);
    }

    function open() {
      var selected = parseDate(input.value);
      if (selected) { shown = new Date(selected.getFullYear(), selected.getMonth(), 1); }
      render();
      popup.hidden = false;
    }

    button.addEventListener('click', function (event) {
      event.preventDefault();
      if (popup.hidden) { open(); } else { close(); }
    });
    input.addEventListener('focus', function () {
      var selected = parseDate(input.value);
      if (selected && /^\d{4}-/.test(input.value)) { input.value = formatDate(selected); }
    });
    document.addEventListener('mousedown', function (event) {
      if (!wrapper.contains(event.target)) { close(); }
    });
    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape') { close(); }
    });
  }

  function start() {
    Array.prototype.forEach.call(document.querySelectorAll('input.sl-date-picker'), init);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }
}());
