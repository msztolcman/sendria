#!/usr/bin/env python

import argparse
from gevent.monkey import patch_all
patch_all()  # must be done before other stuff is imported

from maildump import app, start
from maildump.web import assets


parser = argparse.ArgumentParser()
parser.add_argument('--smtp-ip', default='127.0.0.1')
parser.add_argument('--smtp-port', default=1025, type=int)
parser.add_argument('--http-ip', default='127.0.0.1')
parser.add_argument('--http-port', default=1080, type=int)
parser.add_argument('--db', help='SQLite database - in-memory if missing')
parser.add_argument('-f', '--foreground', help='Run in the foreground', action='store_true')
parser.add_argument('-d', '--debug', help='Run the web app in debug mode', action='store_true')
args = parser.parse_args()

assets.debug = app.debug = args.debug
start(args.http_ip, args.http_port, args.smtp_ip, args.smtp_port, args.db)