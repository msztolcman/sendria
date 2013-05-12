(function($) {
    'use strict';

    $(document).ready(function() {
        // Misc stuff and initialization
        $('.resizer').on('mousedown', function(e) {
            if(e.button != 0) {
                return;
            }
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

        // Message navigation
        $('#messages').on('click', '> tr:not(.deleted)', function() {
            var msg = Message.get($(this).data('messageId'));
            if(msg) {
                msg.select();
                $('#message').show();
            }
        });

        $('.action.delete').on('click', function(e) {
            e.preventDefault();
            var msg = Message.get($('#messages > .selected').data('messageId'));
            if (msg) {
                msg.dom().addClass('deleted');
                restCall('DELETE', '/messages/' + msg.id).fail(function() {
                    msg.dom().removeClass('deleted');
                });
            }
        });

        // Load initial message list
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