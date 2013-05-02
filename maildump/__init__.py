import asyncore
import gevent
from gevent.event import Event
from gevent.pywsgi import WSGIServer
from logbook import Logger

from maildump.db import connect, disconnect, create_tables
from maildump.smtp import smtp_handler, SMTPServer
from maildump.web import app


log = Logger(__name__)
stopper = Event()


def start(http_host, http_port, smtp_host, smtp_port, db_path=None):
    # Webserver
    log.debug('Starting web server')
    WSGIServer((http_host, http_port), app).start()
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
