import asyncore

import gevent
from gevent.event import Event
from logbook import Logger
from socketio.server import SocketIOServer

from maildump.db import connect, disconnect, create_tables
from maildump.smtp import smtp_handler, SMTPServer
from maildump.web import app


log = Logger(__name__)
stopper = Event()
socketio_server = None


def start(http_host, http_port, smtp_host, smtp_port, smtp_auth, db_path=None):
    global socketio_server
    # Webserver
    log.notice('Starting web server on http://{0}:{1}'.format(http_host, http_port))
    socketio_server = SocketIOServer((http_host, http_port), app,
                                     log='default' if app.debug else None)
    socketio_server.start()
    # SMTP server
    log.notice('Starting smtp server on {0}:{1}'.format(smtp_host, smtp_port))
    if smtp_auth:
        log.notice('Enabled SMTP authorization with htpasswd file {0}'.format(smtp_auth))
    SMTPServer((smtp_host, smtp_port), smtp_handler, smtp_auth)
    gevent.spawn(asyncore.loop)
    # Database
    connect(db_path)
    create_tables()
    # Wait....
    try:
        stopper.wait()
    except KeyboardInterrupt:
        print
    else:
        log.debug('Received stop signal')
    # Clean up
    disconnect()
    log.notice('Terminating')


def stop():
    stopper.set()
