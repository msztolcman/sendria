#!/usr/bin/env python

from __future__ import print_function

import argparse
import lockfile
import os
import pkgutil
import signal
import sys

import logbook
from daemon.pidfile import TimeoutPIDLockFile
from .geventdaemon import GeventDaemonContext
from logbook import NullHandler
from logbook.more import ColorizedStderrHandler
from passlib.apache import HtpasswdFile


def read_pidfile(path):
    try:
        with open(path, 'r') as f:
            return int(f.read())
    except Exception as e:
        raise ValueError(e.message)


def terminate_server(sig, frame):
    from maildump import stop

    if sig == signal.SIGINT and os.isatty(sys.stdout.fileno()):
        # Terminate the line containing ^C
        print()
    stop()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--smtp-ip', default='127.0.0.1', metavar='IP', help='SMTP ip (default: 127.0.0.1)')
    parser.add_argument('--smtp-port', default=1025, type=int, metavar='PORT', help='SMTP port (default: 1025)')
    parser.add_argument('--smtp-auth', action='store_true', help='Enable SMTP authorization')
    parser.add_argument('--smtp-username', default='maildump', help='SMTP username (default: maildump)')
    parser.add_argument('--smtp-password', default='maildump', help='SMTP password (default: maildump)')
    parser.add_argument('--http-ip', default='127.0.0.1', metavar='IP', help='HTTP ip (default: 127.0.0.1)')
    parser.add_argument('--http-port', default=1080, type=int, metavar='PORT', help='HTTP port (deault: 1080)')
    parser.add_argument('--db', metavar='PATH', help='SQLite database - in-memory if missing')
    parser.add_argument('--htpasswd', metavar='HTPASSWD', help='Apache-style htpasswd file')
    parser.add_argument('-v', '--version', help='Display the version and exit', action='store_true')
    parser.add_argument('-f', '--foreground', help='Run in the foreground (default if no pid file is specified)',
                        action='store_true')
    parser.add_argument('-d', '--debug', help='Run the web app in debug mode', action='store_true')
    parser.add_argument('-a', '--autobuild-assets', help='Automatically rebuild assets if necessary',
                        action='store_true')
    parser.add_argument('-n', '--no-quit', help='Do not allow clients to terminate the application',
                        action='store_true')
    parser.add_argument('-p', '--pidfile', help='Use a PID file')
    parser.add_argument('--stop', help='Sends SIGTERM to the running daemon (needs --pidfile)', action='store_true')
    args = parser.parse_args()

    if args.version:
        from maildump.util import get_version
        print('MailDump {0}'.format(get_version()))
        sys.exit(0)

    # Do we just want to stop a running daemon?
    if args.stop:
        if not args.pidfile or not os.path.exists(args.pidfile):
            print('PID file not specified or not found')
            sys.exit(1)
        try:
            pid = read_pidfile(args.pidfile)
        except ValueError as e:
            print('Could not read PID file: {0}'.format(e))
            sys.exit(1)
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError as e:
            print('Could not send SIGTERM: {0}'.format(e))
            sys.exit(1)
        sys.exit(0)

    # Default to foreground mode if no pid file is specified
    if not args.pidfile and not args.foreground:
        print('No PID file specified; runnning in foreground')
        args.foreground = True

    # Warn about relative paths and absolutize them
    if args.db and not os.path.isabs(args.db):
        args.db = os.path.abspath(args.db)
        print('Database path is relative, using {0}'.format(args.db))
    if args.htpasswd and not os.path.isabs(args.htpasswd):
        args.htpasswd = os.path.abspath(args.htpasswd)
        print('Htpasswd path is relative, using {0}'.format(args.htpasswd))

    # Check if the password file is valid
    if args.htpasswd and not os.path.isfile(args.htpasswd):
        print('Htpasswd file does not exist')
        sys.exit(1)

    # Check if the static folder is writable
    asset_folder = os.path.join(
        os.path.dirname(pkgutil.get_loader('maildump').get_filename()),
        'static'
    )
    if args.autobuild_assets and not os.access(asset_folder, os.W_OK):
        print('Autobuilding assets requires write access to {0}'.format(asset_folder))
        sys.exit(1)

    daemon_kw = {'monkey_greenlet_report': False,
                 'signal_map': {signal.SIGTERM: terminate_server,
                                signal.SIGINT: terminate_server}}

    if args.foreground:
        # Do not detach and keep std streams open
        daemon_kw.update({'detach_process': False,
                          'stdin': sys.stdin,
                          'stdout': sys.stdout,
                          'stderr': sys.stderr})

    pidfile = None
    if args.pidfile:
        pidfile = os.path.abspath(args.pidfile) if not os.path.isabs(args.pidfile) else args.pidfile
        if os.path.exists(pidfile):
            pid = read_pidfile(pidfile)
            if not os.path.exists(os.path.join('/proc', str(pid))):
                print('Deleting obsolete PID file (process {0} does not exist)'.format(pid))
                os.unlink(pidfile)
        daemon_kw['pidfile'] = TimeoutPIDLockFile(pidfile, 5)

    # Unload threading module to avoid error on exit (it's loaded by lockfile)
    if 'threading' in sys.modules:
        del sys.modules['threading']

    asset_dir = 'maildump/static/assets'
    if not args.autobuild_assets and (not os.path.exists(asset_dir) or not os.listdir(asset_dir)):
        print('Assets not found. Generate assets using webassets -m maildump.web build')
        sys.exit(0)

    context = GeventDaemonContext(**daemon_kw)
    try:
        context.open()
    except lockfile.LockTimeout:
        print('Could not acquire lock on pid file {0}'.format(pidfile))
        print('Check if the daemon is already running.')
        sys.exit(1)
    except KeyboardInterrupt:
        print()
        sys.exit(1)

    with context:
        # Imports are here to avoid importing anything before monkeypatching
        from maildump import app, start
        from maildump.web import assets

        assets.debug = app.debug = args.debug
        assets.auto_build = args.autobuild_assets
        app.config['MAILDUMP_HTPASSWD'] = HtpasswdFile(args.htpasswd) if args.htpasswd else None
        app.config['MAILDUMP_NO_QUIT'] = args.no_quit

        level = logbook.DEBUG if args.debug else logbook.INFO
        format_string = (
            u'[{record.time:%Y-%m-%d %H:%M:%S}]  {record.level_name:<8}  {record.channel}: {record.message}'
        )
        stderr_handler = ColorizedStderrHandler(level=level, format_string=format_string)
        with NullHandler().applicationbound():
            with stderr_handler.applicationbound():
                start(args.http_ip, args.http_port, args.smtp_ip, args.smtp_port, args.smtp_auth, args.smtp_username, args.smtp_password, args.db)


if __name__ == '__main__':
    main()
