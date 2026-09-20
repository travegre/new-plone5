(function ($) {
  'use strict';
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
      $row = $('<tr><td><select name="laboratorij_id" class="nad-lab-select"></select></td><td class="nad-leader"></td><td><select name="nadomestni_vodja_id"></select></td><td><button type="button" class="btn btn-danger nad-remove">−</button></td></tr>');
    }
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