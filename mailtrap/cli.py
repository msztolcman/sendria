import asyncio
import argparse
import os
import pathlib
import sys
import errno
import signal

import aiohttp.web
import daemon
from daemon.pidfile import TimeoutPIDLockFile
from passlib.apache import HtpasswdFile

from . import STATIC_DIR, ASSETS_DIR
from . import logger
from . import smtp
from . import http
from . import db
from . import __version__

shutdown = []


def exit_err(msg, exit_code=1, **kwargs):
    logger.get().msg(msg, **kwargs)
    sys.exit(exit_code)


def parse_argv(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument('--template-header-name', default='', help='Additional name of application')
    parser.add_argument('--template-header-url', default='', help='Url of application')
    parser.add_argument('--smtp-ip', default='127.0.0.1', metavar='IP', help='SMTP ip (default: 127.0.0.1)')
    parser.add_argument('--smtp-port', default=1025, type=int, metavar='PORT', help='SMTP port (default: 1025)')
    parser.add_argument('--smtp-auth', metavar='HTPASSWD',
        help='Apache-style htpasswd file for SMTP authorization. '
            'WARNING: do not rely only on this as a security '
            'mechanism, use also additional methods for securing '
            'MailTrap instance, ie. IP restrictions.')
    parser.add_argument('--http-ip', default='127.0.0.1', metavar='IP', help='HTTP ip (default: 127.0.0.1)')
    parser.add_argument('--http-port', default=1080, type=int, metavar='PORT', help='HTTP port (default: 1080)')
    parser.add_argument('-s', '--db', metavar='PATH', help='Path to SQLite database. Will be created if doesn\'t exist')
    parser.add_argument('--htpasswd', metavar='HTPASSWD', help='Apache-style htpasswd file')
    parser.add_argument('-v', '--version', help='Display the version and exit', action='store_true')
    parser.add_argument('-f', '--foreground', help='Run in the foreground (default if no pid file is specified)',
        action='store_true')
    parser.add_argument('-d', '--debug', help='Run the web app in debug mode', action='store_true')
    parser.add_argument('-a', '--autobuild-assets', help='Automatically rebuild assets if necessary',
        action='store_true')
    parser.add_argument('-n', '--no-quit', help='Do not allow clients to terminate the application',
        action='store_true')
    parser.add_argument('-c', '--no-clear', help='Do not allow clients to clear email database',
        action='store_true')
    parser.add_argument('-p', '--pidfile', help='Use a PID file')
    parser.add_argument('--stop', help='Sends SIGTERM to the running daemon (needs --pidfile)', action='store_true')
    args = parser.parse_args(argv)

    if args.version:
        print('MailTrap %s' % __version__)
        sys.exit(0)

    if args.pidfile:
        args.pidfile = pathlib.Path(args.pidfile)
        if not args.pidfile.is_absolute():
            args.pidfile = args.pidfile.resolve()
            logger.get().msg('INIT: HTTP auth htpasswd path is relative, using %s' % args.pidfile)

    if args.stop:
        return args

    if not args.db:
        exit_err('INIT: Missing database path. Please use --db path/to/db.sqlite')

    args.db = pathlib.Path(args.db)
    if not args.db.is_absolute():
        args.db = args.db.resolve()
        logger.get().msg('INIT: database path is relative, using %s' % args.db)

    # Default to foreground mode if no pid file is specified
    if not args.pidfile and not args.foreground:
        logger.get().msg('INIT: no PID file specified; runnning in foreground')
        args.foreground = True

    # Warn about relative paths and absolutize them
    if args.htpasswd:
        args.htpasswd = pathlib.Path(args.htpasswd)
        if not args.htpasswd.is_absolute():
            args.htpasswd = args.htpasswd.resolve()
            logger.get().msg('INIT: HTTP auth htpasswd path is relative, using %s' % args.htpasswd)
        if not args.htpasswd.is_file():
            exit_err('INIT: HTTP auth htpasswd file does not exist')
    if args.smtp_auth:
        args.smtp_auth = pathlib.Path(args.smtp_auth)
        if not args.smtp_auth.is_absolute():
            args.smtp_auth = args.smtp_auth.resolve()
            logger.get().msg('INIT: SMTP auth htpasswd path is relative, using %s' % args.smtp_auth)
        if not args.smtp_auth.is_file():
            exit_err('INIT: SMTP auth htpasswd file does not exist')

    return args


def pid_exists(pid: int):
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


def read_pidfile(path: pathlib.Path):
    try:
        return int(path.read_text())
    except Exception as e:
        raise ValueError(e.message)


async def terminate_server(sig, loop):
    if sig == signal.SIGINT and os.isatty(sys.stdout.fileno()):
        # Terminate the line containing ^C
        print()

    await asyncio.gather(*shutdown, return_exceptions=True)
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)

    loop.stop()


def run_smtp_server(loop, args, smtp_auth):
    controller = smtp.get_server(args.smtp_ip, args.smtp_port, smtp_auth, args.debug)
    controller.start()

    async def _stop():
        # print('run_smtp_server _stop')
        controller.stop()
    shutdown.append(_stop())


def run_http_server(loop, args, http_auth):
    app = http.setup(args, http_auth)

    runner = aiohttp.web.AppRunner(app)
    loop.run_until_complete(runner.setup())

    site = aiohttp.web.TCPSite(runner, host=args.http_ip, port=args.http_port)
    server = site.start()
    loop.run_until_complete(server)

    async def _stop():
        # print('run_http_server _stop')
        for ws in set(app['websockets']):
            await ws.close(code=aiohttp.WSCloseCode.GOING_AWAY, message='Server shutdown')
        await app.shutdown()

    shutdown.append(_stop())


def setup_db(loop, args):
    loop.run_until_complete(db.set_db(args.db))


def stop(pidfile):
    if not pidfile or not pidfile.exists():
        exit_err('PID file not specified or not found')

    try:
        pid = read_pidfile(pidfile)
    except ValueError as e:
        exit_err('Could not read PID file: %s' % e)

    try:
        os.kill(pid, signal.SIGTERM)
    except OSError as e:
        exit_err('Could not send SIGTERM: %s' % e)


def main():
    args = parse_argv(sys.argv[1:])

    if args.debug:
        logger.get().msg('INIT: debug mode enabled')

    # Do we just want to stop a running daemon?
    if args.stop:
        stop(args.pidfile)
        sys.exit(0)

    # Check if the static folder is writable
    if args.autobuild_assets and not os.access(STATIC_DIR, os.W_OK):
        exit_err('INIT: autobuilding assets requires write access to %s' % STATIC_DIR)

    if not args.autobuild_assets and (not ASSETS_DIR.exists() or not list(ASSETS_DIR.glob('*'))):
        exit_err('INIT: assets not found. Generate assets using: webassets -m mailtrap.build_assets build', 0)

    daemon_kw = {}

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
                logger.get().msg('INIT: deleting obsolete PID file (process %s does not exist)' % pid, pid=pid)
                args.pidfile.unlink()
        daemon_kw['pidfile'] = TimeoutPIDLockFile(str(args.pidfile), 5)

    # Unload threading module to avoid error on exit (it's loaded by lockfile)
    if 'threading' in sys.modules:
        del sys.modules['threading']

    smtp_auth = HtpasswdFile(args.smtp_auth) if args.smtp_auth else None
    http_auth = HtpasswdFile(args.htpasswd) if args.htpasswd else None

    context = daemon.DaemonContext(**daemon_kw)
    with context:
        loop = asyncio.get_event_loop()

        setup_db(loop, args)
        logger.get().msg('INIT: DB configured', db=args.db)

        run_smtp_server(loop, args, smtp_auth)
        logger.get().msg('INIT: smtp server started', smtp_host=args.smtp_ip, smtp_port=args.smtp_port)
        if smtp_auth:
            logger.get().msg('INIT: smtp authorization enabled', password_file=smtp_auth.path)

        run_http_server(loop, args, http_auth)
        logger.get().msg('INIT: http server started', http_host=args.http_ip, http_port=args.http_port,
                url=f'http://{args.http_ip}:{args.http_port}')
        if http_auth:
            logger.get().msg('INIT: http authorization enabled', password_file=http_auth.path)

        signals = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)
        for s in signals:
            loop.add_signal_handler(s, lambda s=s: asyncio.create_task(terminate_server(s, loop)))
        loop.run_forever()

    logger.get().msg('INIT: stop signal received')
    loop.close()

    logger.get().msg('INIT: terminating')
    sys.exit(0)
