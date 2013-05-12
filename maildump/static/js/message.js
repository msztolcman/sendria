// REST
(function($, global) {
    'use strict';
    var messages = {};
    var cleared = new Aborter();

    var Message = global.Message = function Message(msg, loadedEverything) {
        this.sender = msg.sender;
        this.recipients = msg.recipients;
        this.created_at = new Date(msg.created_at);
        this.subject = msg.subject;
        this.id = msg.id;
        this.size = msg.size;
        this._loaded = loadedEverything || false;
        if(this._loaded) {
            this.href = msg.href;
            this.formats = msg.formats;
            this.attachments = msg.attachments;
        }
        else {
            this.href = '#'; // loaded lazily
            this.attachments = []; // loaded lazily
            this.formats = []; // loaded lazily
        }
    };

    Message.prototype = {
        dom: function() {
            return this._dom || (this._dom = renderTemplate('message', this));
        },
        display: function() {
            $('#message-metadata').html(renderTemplate('message-metadata', this));
            $('.action.download a').attr('href', this.href);
        },
        del: function() {
            delete messages[this.id];
            if (this._dom) {
                if(this._dom.hasClass('selected')) {
                    this.deselect();
                    var sibling = this._dom.next();
                    if(!sibling.length) {
                        sibling = this._dom.prev();
                    }
                    sibling.trigger('click');
                }
                this._dom.remove();
                delete this._dom;
            }
        },
        selected: function() {
            return $('#messages > .selected').data('messageId') == this.id;
        },
        select: function() {
            if (!this._dom) {
                console.error('Cannot select message that has not been rendered.');
            }
            $('#message').removeClass('no-message').addClass('loading-message');
            $('#messages > tr.selected').removeClass('selected');
            this.dom().addClass('selected');
            this.load().done(function() {
                $('#message').removeClass('loading-message');
                if (this.selected()) {
                    this.display();
                }
            }).fail(function(){console.log('fail triggered');});
        },
        deselect: function() {
            if (!this._dom) {
                return;
            }

            this._dom.removeClass('selected');
            $('#message').addClass('no-message');
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
                    self.formats = data.formats;
                    deferred.resolveWith(self);
                });
            }
            return deferred.promise();
        }
    };

    Message.get = function(id) {
        return messages[id];
    };

    Message.deleteAll = function() {
        $('#messages > tr').remove();
        $('#message').addClass('no-message');
        messages = {};
        cleared.abort();
    };

    Message.load = function(id) {
        cleared.watch(restCall('GET', '/messages/' + id + '.json')).done(function(msg) {
            Message.add(msg, true);
        });
    };

    Message.add = function(msg, loadedEverything) {
        if (msg.id in messages) {
            console.warn('Message ' + msg.id + ' already exists.');
            return;
        }
        messages[msg.id] = new Message(msg, loadedEverything);
        $('#messages').prepend(messages[msg.id].dom());
    };

    Message.loadAll = function() {
        Message.deleteAll();
        $('#loading-dialog').dialog('open');
        restCall('GET', '/messages/').done(function(data) {
            $.each(data.messages, function(i, msg) {
                Message.add(new Message(msg));
            });
        }).always(function() {
            $('#loading-dialog').dialog('close');
        });
    };
})(jQuery, window);