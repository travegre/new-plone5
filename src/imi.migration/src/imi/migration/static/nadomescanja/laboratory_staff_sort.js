/* Sort the standard Plone 5 Select2 3.x staff widget by visible name.
 * Keep IDs, selected values and Plone's original query/filtering intact.
 */
(function ($) {
    'use strict';

    function install() {
        var field = $('input[name="form.widgets.privzeti_vodja"]');
        if (!field.length) {
            return;
        }
        var instance = field.data('select2');
        if (!instance || !instance.opts || typeof instance.opts.query !== 'function' ||
                instance.opts.query._imiSlovenianSorted) {
            return;
        }
        var originalQuery = instance.opts.query;
        var collator = new Intl.Collator('sl', {sensitivity: 'base'});
        var sortedQuery = function (options) {
            var originalCallback = options.callback;
            var wrapped = $.extend({}, options, {
                callback: function (result) {
                    if (result && $.isArray(result.results)) {
                        result.results.sort(function (a, b) {
                            return collator.compare(a.text || '', b.text || '');
                        });
                    }
                    originalCallback(result);
                }
            });
            return originalQuery.call(this, wrapped);
        };
        sortedQuery._imiSlovenianSorted = true;
        instance.opts.query = sortedQuery;
    }

    $(install);
    // Plone's pat-select2 may initialize after DOM ready.
    $(document).on('patterns-injected', install);
    $(document).on('focus', 'input[name="form.widgets.privzeti_vodja"]', install);
    $(document).on('mousedown', '.select2-container.select2-orderable', install);
}(window.jQuery));
