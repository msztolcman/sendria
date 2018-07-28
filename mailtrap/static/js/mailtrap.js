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
            $(document).on('mousemove.resizer', function(e) {
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
            if(!confirm('Do you really want to terminate the MailTrap application?')) {
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

        if (NotificationUtil.available) {
            var notificationButton = $('nav.app .notifications a');

            var updateNotificationButton = function updateNotificationButton() {
                var enabled = $.jStorage.get('notifications') && NotificationUtil.checkPermission();
                notificationButton.text(enabled ? 'Disable notifications' : 'Enable notifications');
            };

            notificationButton.parent().show();
            notificationButton.on('click', function(e) {
                e.preventDefault();
                switch (NotificationUtil.checkPermission()) {
                    case false: // denied
                        alert('You need to allow notifications via site permissions.');
                        return;
                    case true: // allowed
                        $.jStorage.set('notifications', !$.jStorage.get('notifications'));
                        updateNotificationButton();
                        break;
                    default: // not specified (prompt user)
                        NotificationUtil.requestPermission(function(perm) {
                            $.jStorage.set('notifications', !!perm);
                            updateNotificationButton();
                        });
                        break;

                }
            });
            updateNotificationButton();
        }

        $('#search').on('keyup', function() {
            var term = $(this).val().trim().toLowerCase();
            Message.applyFilter(term);
        });

        // Message navigation
        $('#messages').on('click', '> tr:not(.deleted)', function(e) {
            var msg;
            if (e.ctrlKey) {
                msg = Message.getSelected();
                if (msg) {
                    msg.deselect();
                }
                if (window.getSelection) {
                    window.getSelection().removeAllRanges();
                }
            }
            else {
                msg = Message.get($(this).data('messageId'));
                if (msg && msg != Message.getSelected()) {
                    msg.select();
                    $('#message').show();
                }
            }
        });

        $('.tab.format').on('click', function(e) {
            e.preventDefault();
            var msg = Message.getSelected();
            if (msg) {
                $('.tab.format.selected').removeClass('selected');
                $(this).addClass('selected');
                msg.updateFormat();
            }
        });

        $('.action.delete').on('click', function(e) {
            e.preventDefault();
            var msg = Message.getSelected();
            if (msg) {
                msg.delRemote();
            }
        });

        // Load initial message list
        Message.loadAll();

        // Real-time updates
        var socket = io.connect(undefined, {
            'reconnection limit': 10000,
            'max reconnection attempts': Infinity
        });
        var terminating = false;
        window.onbeforeunload = function() {
            terminating = true;
            socket.disconnect();
            Message.closeNotifications()
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
        }).on('add_message', function(id) {
            Message.load(id, $.jStorage.get('notifications'));
        }).on('delete_message', function(id) {
            var msg = Message.get(id);
            if(msg) {
                msg.del();
            }
        }).on('delete_messages', function() {
            Message.deleteAll();
        });

        // Keyboard shortcuts
        registerHotkeys({
            'del': function() {
                var msg = Message.getSelected();
                if (msg) {
                    msg.delRemote();
                }
            },
            'backspace': function(e) {
                // Backspace causing the iframe to go back even if it's not focused is annoying!
                e.preventDefault();
            },
            'f5': function() {
                // Chrome bug: http://stackoverflow.com/q/5971710/298479
                Message.closeNotifications();
            },
            'ctrl+f5': function() {
                // Chrome bug: http://stackoverflow.com/q/5971710/298479
                Message.closeNotifications();
            },
            'ctrl+r': function() {
                // Chrome bug: http://stackoverflow.com/q/5971710/298479
                Message.closeNotifications();
            },
            'up': function(e) {
                e.preventDefault();
                var msg = Message.getSelected();
                if (!msg) {
                    $('#messages > tr:last').trigger('click');
                    return;
                }
                msg.dom().prevAll(':visible').first().trigger('click');
            },
            'down': function(e) {
                e.preventDefault();
                var msg = Message.getSelected();
                if (!msg) {
                    $('#messages > tr:first').trigger('click');
                    return;
                }
                msg.dom().nextAll(':visible').first().trigger('click');
            },
            'ctrl+up': function(e) {
                e.preventDefault();
                $('#messages > tr:first').trigger('click');
            },
            'ctrl+down': function(e) {
                e.preventDefault();
                $('#messages > tr:last').trigger('click');
            },
            '/': function(e) {
                e.preventDefault();
                $('#search').focus();
            }
        });
    });
})(jQuery);
