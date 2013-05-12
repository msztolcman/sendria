// REST
(function($, global) {
    'use strict';
    var messages = {};

    var Message = global.Message = function Message(msg) {
        this.sender = msg.sender;
        this.recipients = msg.recipients;
        this.created_at = new Date(msg.created_at);
        this.subject = msg.subject;
        this.id = msg.id;
        this.size = msg.size;
    };

    Message.prototype = {
        dom: function() {
            return this._dom || (this._dom = renderTemplate('message', this));
        },
        del: function() {
            delete messages[this.id];
            if (this._dom) {
                if(this._dom.hasClass('selected')) {
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
        select: function() {
            if (!this._dom) {
                console.error('Cannot select message that has not been rendered.');
            }
            $('#messages > tr.selected').removeClass('selected');
            this.dom().addClass('selected');
        }
    };

    Message.get = function(id) {
        return messages[id];
    };

    Message.deleteAll = function() {
        $('#messages > tr').remove();
        messages = {};
    };

    Message.add = function(msg) {
        if (msg.id in messages) {
            console.warn('Message ' + msg.id + ' already exists.');
            return;
        }
        messages[msg.id] = new Message(msg);
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