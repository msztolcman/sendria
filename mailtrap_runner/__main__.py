#!/usr/bin/env python

from __future__ import print_function

import argparse

import errno
import lockfile
import os
import pathlib
import pkgutil
import signal
import sys

import logbook
from daemon.pidfile import TimeoutPIDLockFile
from .geventdaemon import GeventDaemonContext
from logbook import NullHandler, NestedSetup
from logbook.more import ColorizedStderrHandler
from passlib.apache import HtpasswdFile


def pid_exists(pid):
    """Check whether pid exists in the current process table.
    UNIX only.
    Source: https://stackoverflow.com/a/6940314/116153
    """
    if pid < 0:
        return False
    if pid == 0:
        # According to "man 2 kill" PID 0 refers to every process
        # in the process group of the calling process.
        # On certain systems 0 is a valid PID but we have no way
        # to know that in a portable fashion.
        raise ValueError('invalid PID 0')
    try:
        os.kill(pid, 0)
    except OSError as err:
        if err.errno == errno.ESRCH:
            # ESRCH == No such process
            return False
        elif err.errno == errno.EPERM:
            # EPERM clearly means there's a process to deny access to
            return True
        else:
            # According to "man 2 kill" possible error values are
            # (EINVAL, EPERM, ESRCH)
            raise
    else:
        return True


def read_pidfile(path):
    try:
        return int(path.read_text())
    except Exception as e:
        raise ValueError(e.message)


def terminate_server(sig, frame):
    from mailtrap import stop

    if sig == signal.SIGINT and os.isatty(sys.stdout.fileno()):
        # Terminate the line containing ^C
        print()
    stop()


def parse_argv(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument('--smtp-ip', default='127.0.0.1', metavar='IP', help='SMTP ip (default: 127.0.0.1)')
    parser.add_argument('--smtp-port', default=1025, type=int, metavar='PORT', help='SMTP port (default: 1025)')
    parser.add_argument('--smtp-auth', metavar='HTPASSWD', help='Apache-style htpasswd file for SMTP authorization. '
                                                                'WARNING: do not rely only on this as a security '
                                                                'mechanism, use also additional methods for securing '
                                                                'MailTrap instance, ie. IP restrictions.')
    parser.add_argument('--http-ip', default='127.0.0.1', metavar='IP', help='HTTP ip (default: 127.0.0.1)')
    parser.add_argument('--http-port', default=1080, type=int, metavar='PORT', help='HTTP port (default: 1080)')
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
    args = parser.parse_args(argv)

    if args.version:
        from mailtrap.util import get_version
        print('MailTrap %s' % get_version())
        sys.exit(0)

    if args.pidfile:
        args.pidfile = pathlib.Path(args.pidfile).resolve()

    # Default to foreground mode if no pid file is specified
    if not args.pidfile and not args.foreground:
        print('No PID file specified; runnning in foreground')
        args.foreground = True

    # Warn about relative paths and absolutize them
    if args.db and not os.path.isabs(args.db):
        args.db = os.path.abspath(args.db)
        print('Database path is relative, using %s' % args.db)
    if args.htpasswd and not os.path.isabs(args.htpasswd):
        args.htpasswd = os.path.abspath(args.htpasswd)
        print('Htpasswd path is relative, using %s' % args.htpasswd)
    if args.smtp_auth and not os.path.isabs(args.smtp_auth):
        args.smtp_auth = os.path.abspath(args.smtp_auth)
        print('SMTP auth htpasswd path is relative, using %s' % args.smtp_auth)

    # Check if the password file is valid
    if args.htpasswd and not os.path.isfile(args.htpasswd):
        print('Htpasswd file does not exist')
        sys.exit(1)
    if args.smtp_auth and not os.path.isfile(args.smtp_auth):
        print('SMTP auth htpasswd file does not exist')
        sys.exit(1)

    return args


def main():
    args = parse_argv(sys.argv[1:])

    # Do we just want to stop a running daemon?
    if args.stop:
        if not args.pidfile or not args.pidfile.exists():
            print('PID file not specified or not found')
            sys.exit(1)
        try:
            pid = read_pidfile(args.pidfile)
        except ValueError as e:
            print('Could not read PID file: %s' % e)
            sys.exit(1)
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError as e:
            print('Could not send SIGTERM: %s' % e)
            sys.exit(1)
        sys.exit(0)

    # Check if the static folder is writable
    statics_dir = pathlib.Path(pkgutil.get_loader('mailtrap').get_filename()).parent / 'static'
    if args.autobuild_assets and not os.access(statics_dir, os.W_OK):
        print('Autobuilding assets requires write access to %s' %  statics_dir)
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

    if args.pidfile:
        if args.pidfile.exists():
            pid = read_pidfile(args.pidfile)
            if not pid_exists(pid):
                print('Deleting obsolete PID file (process %s does not exist)' % pid)
                args.pidfile.unlink()
        daemon_kw['pidfile'] = TimeoutPIDLockFile(str(args.pidfile), 5)

    # Unload threading module to avoid error on exit (it's loaded by lockfile)
    if 'threading' in sys.modules:
        del sys.modules['threading']

    asset_dir = statics_dir / 'assets'
    if not args.autobuild_assets and (not asset_dir.exists() or not list(asset_dir.glob('*'))):
        print('Assets not found. Generate assets using: webassets -m mailtrap.web build')
        sys.exit(0)

    context = GeventDaemonContext(**daemon_kw)
    try:
        context.open()
    except lockfile.LockTimeout:
        print('Could not acquire lock on pid file %s' % args.pidfile)
        print('Check if the daemon is already running.')
        sys.exit(1)
    except KeyboardInterrupt:
        print()
        sys.exit(1)

    with context:
        # Imports are here to avoid importing anything before monkeypatching
        from mailtrap import app, start
        from mailtrap.web import assets

        assets.debug = app.debug = args.debug
        assets.auto_build = args.autobuild_assets
        app.config['MAILTRAP_HTPASSWD'] = HtpasswdFile(args.htpasswd) if args.htpasswd else None
        app.config['MAILTRAP_NO_QUIT'] = args.no_quit
        smtp_auth = HtpasswdFile(args.smtp_auth) if args.smtp_auth else None

        level = logbook.DEBUG if args.debug else logbook.INFO
        format_string = (
            u'[{record.time:%Y-%m-%d %H:%M:%S}]  {record.level_name:<8}  {record.channel}: {record.message}'
        )
        stderr_handler = ColorizedStderrHandler(level=level, format_string=format_string)

        with NestedSetup([NullHandler(), stderr_handler]).applicationbound():
            start(args.http_ip, args.http_port, args.smtp_ip, args.smtp_port, smtp_auth, args.db, args.debug)


if __name__ == '__main__':
    main()
