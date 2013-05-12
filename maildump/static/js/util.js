// Templating
(function($, global) {
    'use strict';
    var templates = null;

    Handlebars.registerHelper('join', function(context, opts) {
        return context.join(', ');
    });

    Handlebars.registerHelper('date', function(context, opts) {
        return moment(context).format(opts.hash.format || 'YYYY-MM-DD HH:mm:ss');
    });

    function loadTemplates() {
        if(!$.isReady) {
            console.error('Tried loading templates before DOMReady');
            console.trace();
            return false;
        }
        templates = {};
        $('script.template').each(function() {
            var $this = $(this);
            templates[$this.data('id')] = Handlebars.compile($this.html().trim());
        }).remove();
        return true;
    }

    global.renderTemplate = function renderTemplate(name, context) {
        if(templates === null && !loadTemplates()) {
            return 'Cannot use templates before DOMReady. ';
        }
        var tplFunc = templates[name] || function() {
            console.error('Template not found: ' + name);
            console.trace();
            return 'Template "' + name + '" not found. ';
        };
        return $($.parseHTML(tplFunc(context || {})));
    };
})(jQuery, window);

// REST
(function($, global) {
    'use strict';
    global.restCall = function restCall(method, path) {
        return $.ajax({
            url: path,
            type: method
        }).fail(function(xhr, status, error) {
            alert('REST call failed: ' + method + ' ' + path + '\nStatus: ' + status + '\nError: ' + error);
        });
    };
})(jQuery, window);
