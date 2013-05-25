// Templating
(function($, global) {
    'use strict';
    var templates = null;

    Handlebars.registerHelper('join', function(context, opts) {
        return context.join(', ');
    });

    Handlebars.registerHelper('date', function(context, opts) {
        var ts = moment(context);
        ts.add('minutes', -ts.zone());
        return ts.format(opts.hash.format || 'YYYY-MM-DD HH:mm:ss');
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


// Deferred aborter
(function($, global) {
    'use strict';

    /*
    * Usage: Create a new Aborter instance and call its .abort() method whenever
    * you want to abort all requests started before.
    * Whenever you start a request that should be abortable pass it to .watch()
    * which will reject reject it on abort and do not use the deferred passed to
    * it since it always returns a new deferred (needed in case someone passes) a
    * promise object instead of a real deferred.
    * */

    var Aborter = global.Aborter = function Aborter() {
        this.aborted = $.Deferred();
    };
    Aborter.prototype = {
        abort: function() {
            this.aborted.reject();
            this.aborted = $.Deferred();
        },
        watch: function(deferred) {
            // We need to create a new deferred in case someone passed us a promise object
            var newDeferred = $.Deferred();
            // Forward original deferred's events
            deferred.then(function() {
                newDeferred.resolveWith(this, Array.prototype.slice.call(arguments));
            }, function() {
                newDeferred.rejectWith(this, Array.prototype.slice.call(arguments));
            });
            // Add out own event to reject in case of abortion
            this.aborted.fail(function() {
                newDeferred.rejectWith(this, Array.prototype.slice.call(arguments));
            });
            return newDeferred;
        }
    };
})(jQuery, window);


// Hotkey wrapper
(function($, global) {
    'use strict';

    global.registerHotkeys = function registerHotkeys(map) {
        $.each(map, function(key, fn) {
            $(document).on('keydown', null, key, fn);
        });
    };
})(jQuery, window);


// Notifications
(function($, global) {
    'use strict';

    var permissionMap = {
        // mozilla / standard
        'granted': true,
        'default': undefined,
        'denied': false,
        // old webkit
        0: true,
        1: undefined,
        2: false
    };

    function show(title, text, opts, timeout) {
        opts = $.extend({}, opts || {});
        opts.body = text;
        var notification = new Notification(title, opts);
        if (timeout) {
            window.setTimeout(function() {
                notification.close();
            }, timeout);
        }
        return function() {
            notification.close();
        };
    }

    function checkPermission() {
        var perm = Notification.permission;
        // yay for webkit not having this option: http://code.google.com/p/chromium/issues/detail?id=244030
        if (perm === undefined && window.webkitNotifications) {
            perm = window.webkitNotifications.checkPermission();
        }
        return permissionMap[perm];
    }

    function requestPermission(callback) {
        Notification.requestPermission(function(response) {
            callback(permissionMap[response]);
        });
    }

    if (window.Notification) {
        global.NotificationUtil = {
            available: true,
            show: show,
            checkPermission: checkPermission,
            requestPermission: requestPermission
        };
    }
    else {
        global.NotificationUtil = {
            available: false
        };
    }
})(jQuery, window);