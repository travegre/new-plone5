(function ($) {
  'use strict';
  function slovenianKey(value) {
    return String(value || '').toLocaleLowerCase().replace(/č/g, 'c~')
      .replace(/š/g, 's~').replace(/ž/g, 'z~');
  }
  function sortEmployeeSelect(select) {
    var options = Array.prototype.slice.call(select.options);
    var empty = options.filter(function (option) { return !option.value; });
    var people = options.filter(function (option) { return !!option.value; });
    people.sort(function (a, b) {
      var x = slovenianKey(a.text), y = slovenianKey(b.text);
      return x < y ? -1 : (x > y ? 1 : 0);
    });
    empty.concat(people).forEach(function (option) { select.appendChild(option); });
  }
  function sortEmployeeSelectors(root) {
    $(root).find('select[name="nadomestni_vodja_id"]').each(function () {
      sortEmployeeSelect(this);
    });
  }
  $(function () {
    sortEmployeeSelectors(document);
  });
  function removeRow() { $(this).closest('tr').remove(); }
  $(document).on('click', '.nad-remove', removeRow);
  $('#nad-add').on('click', function () {
    var $source = $('#nadomescanja-rows tr:first');
    var $row;
    if ($source.length) {
      $row = $source.clone(false);
      $row.find('select').val('');
      $row.find('.nad-leader').text('');
    } else {
      $row = $('#nad-row-template').clone(false).removeAttr('id');
    }
    sortEmployeeSelectors($row);
    $('#nadomescanja-rows').append($row);
  });
  $(document).on('change', '.nad-lab-select', function () {
    var $row = $(this).closest('tr');
    var lab = $(this).val();
    var $template = $('#nad-lab-data option[value="' + lab.replace(/"/g, '\\"') + '"]');
    if ($template.length) {
      $row.find('.nad-leader').text($template.attr('data-leader-name') || '');
      var leader = $template.attr('data-leader-id') || '';
      $row.find('select[name="nadomestni_vodja_id"] option').show().filter('[value="' + leader.replace(/"/g, '\\"') + '"]').hide();
      if ($row.find('select[name="nadomestni_vodja_id"]').val() === leader) $row.find('select[name="nadomestni_vodja_id"]').val('');
    }
  });
}(jQuery));