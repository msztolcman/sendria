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
        html: function() {
            return this.dom || (this.dom = renderTemplate('message', this));
        },
        del: function() {
            delete messages[this.id];
            if (this.dom) {
                this.dom.remove();
                delete this.dom;
            }
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
        $('#messages').prepend(messages[msg.id].html());
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