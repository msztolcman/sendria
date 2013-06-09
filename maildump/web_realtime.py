from flask import current_app, request
from socketio import socketio_manage
from socketio.namespace import BaseNamespace


def broadcast(event, *args):
    from maildump import socketio_server  # avoid circular import
    pkt = dict(type='event', name=event, args=args, endpoint='')
    for sessid, socket in socketio_server.sockets.iteritems():
        socket.send_packet(pkt)


def handle_socketio_request(remaining):
    try:
        socketio_manage(request.environ, {'': BaseNamespace}, request)
    except Exception:
        current_app.logger.exception('Exception while handling socketio connection')
        raise
    return current_app.response_class()
