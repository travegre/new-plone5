(function () {
  'use strict';

  var MONTHS = [
    'januar', 'februar', 'marec', 'april', 'maj', 'junij',
    'julij', 'avgust', 'september', 'oktober', 'november', 'december'
  ];
  var DAYS = ['Pon', 'Tor', 'Sre', 'Čet', 'Pet', 'Sob', 'Ned'];

  function pad(value) {
    return value < 10 ? '0' + value : String(value);
  }

  function iso(date) {
    return date.getFullYear() + '-' + pad(date.getMonth() + 1) + '-' + pad(date.getDate());
  }

  function display(value) {
    var parts = String(value || '').split('-');
    if (parts.length !== 3) { return value || ''; }
    return parts[2] + '.' + parts[1] + '.' + parts[0];
  }

  function parse(value) {
    var parts = String(value || '').split('-');
    if (parts.length !== 3) { return new Date(); }
    var date = new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]));
    return isNaN(date.getTime()) ? new Date() : date;
  }

  function injectStyle() {
    if (document.getElementById('imi-legacy-date-picker-style')) { return; }
    var style = document.createElement('style');
    style.id = 'imi-legacy-date-picker-style';
    style.textContent =
      '.imi-date-wrap{position:relative;display:inline-block}' +
      '.imi-date-display{width:9.5em;background:#fff;cursor:pointer}' +
      '.imi-date-popup{position:absolute;z-index:10000;top:100%;left:0;margin-top:3px;padding:8px;background:#fff;border:1px solid #888;box-shadow:0 2px 8px rgba(0,0,0,.2);font-family:Arial,Helvetica,sans-serif;color:#333}' +
      '.imi-date-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:6px}' +
      '.imi-date-head button{border:0;background:transparent;cursor:pointer;font-size:18px;line-height:20px;padding:0 6px}' +
      '.imi-date-title{min-width:120px;text-align:center;font-weight:bold}' +
      '.imi-date-table{border-collapse:collapse;font-size:12px}' +
      '.imi-date-table th,.imi-date-table td{width:28px;height:26px;padding:0;text-align:center;border:0}' +
      '.imi-date-table th{font-weight:bold;color:#555}' +
      '.imi-date-table button{width:26px;height:24px;padding:0;border:0;background:transparent;cursor:pointer;color:#333}' +
      '.imi-date-table button:hover,.imi-date-table button:focus{background:#eee}' +
      '.imi-date-table button.selected{background:#654fa4;color:#fff}' +
      '.imi-date-empty{visibility:hidden}';
    document.head.appendChild(style);
  }

  function enhance(input) {
    if (input.getAttribute('data-imi-date-ready') === '1') { return; }
    input.setAttribute('data-imi-date-ready', '1');
    input.setAttribute('lang', 'sl');

    var initial = input.value;
    input.type = 'hidden';

    var wrap = document.createElement('span');
    wrap.className = 'imi-date-wrap';
    input.parentNode.insertBefore(wrap, input);
    wrap.appendChild(input);

    var visible = document.createElement('input');
    visible.type = 'text';
    visible.readOnly = true;
    visible.className = 'imi-date-display';
    visible.value = display(initial);
    visible.setAttribute('aria-label', 'Izberite datum');
    wrap.appendChild(visible);

    var popup = document.createElement('div');
    popup.className = 'imi-date-popup';
    popup.hidden = true;
    wrap.appendChild(popup);

    var shown = parse(initial);

    function close() {
      popup.hidden = true;
    }

    function choose(date) {
      input.value = iso(date);
      visible.value = display(input.value);
      input.dispatchEvent(new Event('change', {bubbles: true}));
      close();
    }

    function render() {
      popup.innerHTML = '';

      var head = document.createElement('div');
      head.className = 'imi-date-head';
      var prev = document.createElement('button');
      prev.type = 'button';
      prev.setAttribute('aria-label', 'Prejšnji mesec');
      prev.textContent = '‹';
      var title = document.createElement('span');
      title.className = 'imi-date-title';
      title.textContent = MONTHS[shown.getMonth()] + ' ' + shown.getFullYear();
      var next = document.createElement('button');
      next.type = 'button';
      next.setAttribute('aria-label', 'Naslednji mesec');
      next.textContent = '›';
      head.appendChild(prev);
      head.appendChild(title);
      head.appendChild(next);
      popup.appendChild(head);

      prev.addEventListener('click', function () {
        shown = new Date(shown.getFullYear(), shown.getMonth() - 1, 1);
        render();
      });
      next.addEventListener('click', function () {
        shown = new Date(shown.getFullYear(), shown.getMonth() + 1, 1);
        render();
      });

      var table = document.createElement('table');
      table.className = 'imi-date-table';
      var thead = document.createElement('thead');
      var hr = document.createElement('tr');
      DAYS.forEach(function (name) {
        var th = document.createElement('th');
        th.textContent = name;
        hr.appendChild(th);
      });
      thead.appendChild(hr);
      table.appendChild(thead);

      var tbody = document.createElement('tbody');
      var first = new Date(shown.getFullYear(), shown.getMonth(), 1);
      var offset = (first.getDay() + 6) % 7;
      var lastDay = new Date(shown.getFullYear(), shown.getMonth() + 1, 0).getDate();
      var selected = input.value;
      var day = 1;

      for (var row = 0; row < 6 && day <= lastDay; row += 1) {
        var tr = document.createElement('tr');
        for (var col = 0; col < 7; col += 1) {
          var td = document.createElement('td');
          if ((row === 0 && col < offset) || day > lastDay) {
            td.className = 'imi-date-empty';
            td.textContent = '0';
          } else {
            (function (number) {
              var date = new Date(shown.getFullYear(), shown.getMonth(), number);
              var button = document.createElement('button');
              button.type = 'button';
              button.textContent = String(number);
              if (iso(date) === selected) { button.className = 'selected'; }
              button.addEventListener('click', function () { choose(date); });
              td.appendChild(button);
            }(day));
            day += 1;
          }
          tr.appendChild(td);
        }
        tbody.appendChild(tr);
      }
      table.appendChild(tbody);
      popup.appendChild(table);
    }

    visible.addEventListener('click', function () {
      shown = parse(input.value);
      render();
      popup.hidden = !popup.hidden;
    });
    visible.addEventListener('keydown', function (event) {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        shown = parse(input.value);
        render();
        popup.hidden = false;
      } else if (event.key === 'Escape') {
        close();
      }
    });
    document.addEventListener('mousedown', function (event) {
      if (!wrap.contains(event.target)) { close(); }
    });
  }

  function init() {
    injectStyle();
    Array.prototype.forEach.call(document.querySelectorAll('input[type="date"]'), enhance);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
}());
