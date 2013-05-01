import asyncore
from gevent.pywsgi import WSGIServer
from gevent.monkey import patch_all
from logbook import Logger

from maildump.db import connect, create_tables
from maildump.smtp import smtp_handler, SMTPServer
from maildump.web import app


log = Logger(__name__)


def start(http_host, http_port, smtp_host, smtp_port, db_path=None):
    # gevent patches
    patch_all()
    # Webserver
    log.debug('Starting web server')
    WSGIServer((http_host, http_port), app).start()
    # SMTP server
    log.debug('Starting smtp server')
    SMTPServer((smtp_host, smtp_port), smtp_handler)
    # Database
    connect(db_path)
    create_tables()

    log.debug('Entering event loop')
    try:
        asyncore.loop()
    except KeyboardInterrupt:
        pass