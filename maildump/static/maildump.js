(function($) {
    $(document).ready(function() {
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

        function restCall(method, path) {
            return $.ajax({
                url: path,
                type: method
            }).fail(function(xhr, status, error) {
                alert('REST call failed: ' + method + ' ' + path + '\nStatus: ' + status + '\nError: ' + error);
            });
        }

        // Top nav actions
        $('nav.app .quit a').on('click', function(e) {
            e.preventDefault();
            if(!confirm('Do you really want to terminate the MailDump application?')) {
                return;
            }
            restCall('DELETE', '/').done(function() {
                alert('Terminated.');
                // TODO: Remove this message after we handle websocket events
            });
        });

        $('nav.app .clear a').on('click', function(e) {
            e.preventDefault();
            if (!confirm('Do you really want to delete all messages?')) {
                return;
            }
            restCall('DELETE', '/messages/').done(function() {
                alert('Deleted all messages');
                // TODO: Remove this message after we handle websocket events
            });
        });
    });
})(jQuery);