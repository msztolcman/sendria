// REST
(function($, global) {
    'use strict';
    var messages = {};
    var cleared = new Aborter();
    var filterTerm = '';

    function addCacheBuster(formats) {
        $.each(formats, function(format, url) {
            formats[format] = url + '?_=' + (new Date().getTime());
        });
        return formats;
    }

    var Message = global.Message = function Message(msg, loadedEverything) {
        this._loaded = loadedEverything || false;
        this._deleted = false;
        this.id = msg.id;
        this.sender = msg.sender;
        this.recipients = msg.recipients;
        this.created_at = new Date(msg.created_at);
        this.subject = msg.subject;
        this.size = msg.size;
        if(this._loaded) {
            this.href = msg.href;
            this.formats = addCacheBuster(msg.formats);
            this.attachments = msg.attachments;
        }
        else {
            this.href = '#'; // loaded lazily
            this.attachments = []; // loaded lazily
            this.formats = {}; // loaded lazily
        }
    };

    Message.prototype = {
        dom: function() {
            return this._dom || (this._dom = renderTemplate('message', this));
        },
        display: function() {
            var self = this;
            $('#message-metadata').html(renderTemplate('message-metadata', this));
            $('.action.download a').attr('href', this.href);
            $('.views .format').each(function() {
                var $this = $(this);
                var format = $this.data('messageFormat');
                $this.toggle(format in self.formats);
                $('a', this).attr('href', self.formats[format] || '#');
            }).removeClass('selected').filter(':visible:first').addClass('selected');
            this.updateFormat();
        },
        updateFormat: function() {
            var format = $('.views .format.selected').data('messageFormat');
            if ($('#message-body').attr('src') != this.formats[format]) {
                $('#message-body').attr('src', this.formats[format]);
            }
        },
        del: function() {
            delete messages[this.id];
            this.selectSibling();
            this.closeNotification();
            if (this._dom) {
                this._dom.remove();
                delete this._dom;
            }
        },
        delRemote: function() {
            var self = this;
            if (this._deleted) {
                return;
            }
            this._deleted = true;
            this.dom().addClass('deleted');
            this.selectSibling();
            this.closeNotification();
            restCall('DELETE', '/messages/' + this.id).fail(function() {
                self._deleted = false;
                self.dom().removeClass('deleted');
            });
        },
        selected: function() {
            return $('#messages > .selected').data('messageId') == this.id;
        },
        selectSibling: function() {
            if (!this._dom || !this.selected()) {
                return;
            }
            this.deselect();
            var sibling = this._dom.nextAll(':visible:not(.deleted)').first();
            if (!sibling.length) {
                sibling = this._dom.prevAll(':visible:not(.deleted)').first();
            }
            sibling.trigger('click');
        },
        select: function() {
            if (!this._dom) {
                console.error('Cannot select message that has not been rendered.');
            }
            var row = this.dom();
            this.closeNotification();
            $('#message').removeClass('no-message').addClass('loading-message');
            $('#messages > tr.selected').removeClass('selected');
            row.addClass('selected');
            if (row.position().top <= 0 || row.position().top + row.height() > row.offsetParent().height()) {
                // Scroll to row if necessary
                if (row.index() == 0) {
                    // First element? Include header
                    row.closest('table').find('thead')[0].scrollIntoView();
                }
                else {
                    row[0].scrollIntoView();
                }
            }
            $('#message-body').attr('src', 'about:blank');
            this.load().done(function() {
                $('#message').removeClass('loading-message');
                if (this.selected()) {
                    this.display();
                }
            });
        },
        deselect: function() {
            if (!this._dom) {
                return;
            }

            this._dom.removeClass('selected');
            $('#message').addClass('no-message');
            $('#message-body').attr('src', 'about:blank');
        },
        load: function() {
            var self = this;
            var deferred = $.Deferred();
            if(this._loaded) {
                deferred.resolveWith(this);
            }
            else {
                cleared.watch(restCall('GET', '/messages/' + this.id + '.json')).done(function(data) {
                    self._loaded = true;
                    self.href = data.href;
                    self.attachments = data.attachments;
                    self.formats = addCacheBuster(data.formats);
                    deferred.resolveWith(self);
                });
            }
            return deferred.promise();
        },
        showNotification: function() {
            var self = this;
            var msg = 'From ' + this.sender + '\xa0 to \xa0' + this.recipients.to.join(', ');
            this._closeNotification = NotificationUtil.show(this.subject, msg, {
                icon: '/static/images/icon_80x80.png'
            }, 10000, function() {
                self.select();
            });
        },
        closeNotification: function() {
            if (this._closeNotification) {
                this._closeNotification();
                delete this._closeNotification;
            }
        }
    };

    Message.get = function(id) {
        return messages[id];
    };

    Message.getSelected = function() {
        return Message.get($('#messages > .selected').data('messageId'));
    };

    Message.deleteAll = function() {
        Message.closeNotifications();
        $('#messages > tr').remove();
        $('#message').addClass('no-message');
        messages = {};
        cleared.abort();
    };

    Message.closeNotifications = function() {
        $.each(messages, function(id, message) {
            message.closeNotification();
        });
    };

    Message.load = function(id, notify) {
        cleared.watch(restCall('GET', '/messages/' + id + '.json')).done(function(msg) {
            var message = Message.add(msg, true);
            Message.applyFilter();
            if (notify) {
                message.showNotification();
            }
        });
    };

    Message.add = function(msg, loadedEverything) {
        if (msg.id in messages) {
            console.warn('Message ' + msg.id + ' already exists.');
            return;
        }
        messages[msg.id] = new Message(msg, loadedEverything);
        $('#messages').prepend(messages[msg.id].dom());
        return messages[msg.id];
    };

    Message.loadAll = function() {
        Message.deleteAll();
        $('#loading-dialog').dialog('open');
        restCall('GET', '/messages/').done(function(data) {
            $.each(data.messages, function(i, msg) {
                Message.add(new Message(msg));
            });
            Message.applyFilter();
        }).always(function() {
            $('#loading-dialog').dialog('close');
        });
    };

    Message.applyFilter = function(term) {
        if(term !== undefined) {
            filterTerm = term;
        }
        var all = $('#messages > tr').show();
        if (filterTerm) {
            all.filter(function() {
                return !~$(this).text().toLowerCase().indexOf(filterTerm);
            }).hide();
            var selected = Message.getSelected();
            if(selected && !selected.dom().is(':visible')) {
                selected.deselect();
            }
        }
    }
})(jQuery, window);
