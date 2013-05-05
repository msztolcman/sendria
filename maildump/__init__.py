import asyncore
import gevent
from gevent.event import Event
from logbook import Logger
from socketio.server import SocketIOServer

from maildump.db import connect, disconnect, create_tables
from maildump.smtp import smtp_handler, SMTPServer
from maildump.web import app
from maildump.web_realtime import broadcast


log = Logger(__name__)
stopper = Event()
socketio_server = None


def start(http_host, http_port, smtp_host, smtp_port, db_path=None):
    global socketio_server
    # Webserver
    log.debug('Starting web server')
    socketio_server = SocketIOServer((http_host, http_port), app)
    socketio_server.start()
    # SMTP server
    log.debug('Starting smtp server')
    SMTPServer((smtp_host, smtp_port), smtp_handler)
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
    log.info('Terminating')


def stop():
    stopper.set()
