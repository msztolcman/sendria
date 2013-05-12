(function($) {
    'use strict';
    var templates = {};

    Handlebars.registerHelper('join', function(context, opts) {
        return context.join(', ');
    });

    Handlebars.registerHelper('date', function(context, opts) {
        return moment(context).format(opts.hash.format || 'YYYY-MM-DD HH:mm:ss');
    });

    function restCall(method, path) {
        return $.ajax({
            url: path,
            type: method
        }).fail(function(xhr, status, error) {
            alert('REST call failed: ' + method + ' ' + path + '\nStatus: ' + status + '\nError: ' + error);
        });
    }

    function Message(msg) {
        this.sender = msg.sender;
        this.recipients = msg.recipients;
        this.created_at = new Date(msg.created_at);
        this.subject = msg.subject;
        this.id = msg.id;
        this.size = msg.size;
    }
    Message.prototype = {
        html: function() {
            return this.dom || (this.dom = $($.parseHTML(templates['message'](this))));
        },
        del: function() {
            delete Message.messages[this.id];
            if(this.dom) {
                this.dom.remove();
            }
        }
    };
    Message.messages = {};
    Message.get = function(id) {
        return Message.messages[id];
    };
    Message.deleteAll = function() {
        $('#messages > tr').remove();
        Message.messages = {};
    };
    Message.add = function(msg) {
        if (msg.id in Message.messages) {
            console.warn('Message ' + msg.id + ' already exists.');
            return;
        }
        Message.messages[msg.id] = new Message(msg)        ;
        $('#messages').prepend(Message.messages[msg.id].html());
    };
    Message.loadAll = function() {
        Message.deleteAll();
        $('#loading-dialog').dialog('open');
        restCall('GET' , '/messages/').done(function(data) {
            $.each(data.messages, function(i, msg) {
                Message.add(new Message(msg));
            });
        }).always(function() {
            $('#loading-dialog').dialog('close');
        });
    };

    $(document).ready(function() {
        // Misc stuff and initialization
        $('.resizer').on('mousedown', function(e) {
            var $this = $(this);
            var target = $this.data('sibling') == 'prev' ? $this.prev() : $this.next();
            e.preventDefault();
            $(document).on('mousemove.resizer',function(e) {
                e.preventDefault();
                target.css('height', e.clientY - target.offset().top);
            }).on('mouseup.resizer', function(e) {
                e.preventDefault();
                $(document).off('.resizer');
            });
        });

        $('#disconnected-dialog, #loading-dialog').dialog({
            autoOpen: false,
            closeOnEscape: false,
            dialogClass: 'no-close',
            draggable: false,
            modal: true,
            resizable: false,
            title: ''
        });

        $('script.template').each(function() {
            var $this = $(this);
            templates[$this.data('id')] = Handlebars.compile($(this).html());
        });

        // Top nav actions
        $('nav.app .quit a').on('click', function(e) {
            e.preventDefault();
            if(!confirm('Do you really want to terminate the MailDump application?')) {
                return;
            }
            restCall('DELETE', '/');
        });

        $('nav.app .clear a').on('click', function(e) {
            e.preventDefault();
            if (!confirm('Do you really want to delete all messages?')) {
                return;
            }
            restCall('DELETE', '/messages/');
        });

        Message.loadAll();

        // Real-time updates
        var socket = io.connect();
        var terminating = false;
        window.onbeforeunload = function() {
            terminating = true;
            socket.disconnect();
        };
        socket.on('connect', function() {
            $('#disconnected-dialog').dialog('close');
        }).on('reconnect', function() {
            Message.loadAll();
        }).on('disconnect', function() {
            if(terminating) {
                return;
            }
            $('#loading-dialog').dialog('close');
            $('#disconnected-dialog').dialog('open');
        }).on('add_message',function(id) {
            restCall('GET', '/messages/' + id + '.json').done(function(msg) {
                Message.add(msg);
            });
        }).on('delete_message',function(id) {
            var msg = Message.get(id);
            if(msg) {
                msg.del();
            }
        }).on('delete_messages', function() {
            Message.deleteAll();
        });
    });
})(jQuery);