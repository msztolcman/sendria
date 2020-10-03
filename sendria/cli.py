__all__ = ['main', 'terminate_server']

import asyncio
import argparse
import errno
import os
import pathlib
import signal
import sys

import aiohttp.web
import daemon
from daemon.pidfile import TimeoutPIDLockFile
from passlib.apache import HtpasswdFile

from . import STATIC_DIR, ASSETS_DIR
from . import __version__
from . import db
from . import http
from . import logger
from . import notifier
from . import smtp
from . import callback

SHUTDOWN = []


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
            'Sendria instance, ie. IP restrictions.')
    parser.add_argument('--http-ip', default='127.0.0.1', metavar='IP', help='HTTP ip (default: 127.0.0.1)')
    parser.add_argument('--http-port', default=1080, type=int, metavar='PORT', help='HTTP port (default: 1080)')
    parser.add_argument('-s', '--db', metavar='PATH', help='Path to SQLite database. Will be created if doesn\'t exist')
    parser.add_argument('--http-auth', metavar='HTPASSWD', help='Apache-style htpasswd file')
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
    parser.add_argument('--callback-webhook-url',
        help='URL where webhook shoud be sent. If empty (default) then no webhook is sent.')
    parser.add_argument('--callback-webhook-method', default='POST',
        help='HTTP method for webhook')
    parser.add_argument('--callback-webhook-auth',
        help='Optional credentials ("login:password") for webhook (only Basic Auth supported). If empty, then no '
            'authorization header is sent')

    args = parser.parse_args(argv)

    if args.pidfile:
        args.pidfile = pathlib.Path(args.pidfile)
        if not args.pidfile.is_absolute():
            args.pidfile = args.pidfile.resolve()

    if args.stop or args.version:
        return args

    if not args.db:
        exit_err('Missing database path. Please use --db path/to/db.sqlite')

    args.db = pathlib.Path(args.db)
    if not args.db.is_absolute():
        args.db = args.db.resolve()

    # Default to foreground mode if no pid file is specified
    if not args.pidfile and not args.foreground:
        logger.get().msg('no PID file specified; runnning in foreground')
        args.foreground = True

    # Warn about relative paths and absolutize them
    if args.http_auth:
        args.http_auth = pathlib.Path(args.http_auth)
        if not args.http_auth.is_absolute():
            args.http_auth = args.http_auth.resolve()
        if not args.http_auth.is_file():
            exit_err('HTTP auth htpasswd file does not exist')

        args.http_auth = HtpasswdFile(args.http_auth)

    if args.smtp_auth:
        args.smtp_auth = pathlib.Path(args.smtp_auth)
        if not args.smtp_auth.is_absolute():
            args.smtp_auth = args.smtp_auth.resolve()
        if not args.smtp_auth.is_file():
            exit_err('SMTP auth htpasswd file does not exist')

        args.smtp_auth = HtpasswdFile(args.smtp_auth)

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


def read_pidfile(path: pathlib.Path) -> int:
    try:
        return int(path.read_text().strip())
    except Exception as exc:
        raise ValueError(exc.message)


async def terminate_server(sig: int, loop: asyncio.AbstractEventLoop) -> None:
    if sig == signal.SIGINT and os.isatty(sys.stdout.fileno()):
        # Terminate the line containing ^C
        print()

    await asyncio.gather(*SHUTDOWN, return_exceptions=True)

    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)

    loop.stop()


def run_sendria_servers(loop, args: argparse.Namespace) -> None:
    # initialize db
    loop.run_until_complete(db.setup(args.db))

    # initialize and start webhooks
    callbacks_enabled = callback.setup(args)
    if callbacks_enabled:
        loop.create_task(callback.send_messages())

    # start smtp server
    smtp.run(args.smtp_ip, args.smtp_port, args.smtp_auth, args.debug)
    logger.get().msg('smtp server started', host=args.smtp_ip, port=args.smtp_port,
        auth='enabled' if args.smtp_auth else 'disabled',
        password_file=str(args.smtp_auth.path) if args.smtp_auth else None,
        url=f'smtp://{args.smtp_ip}:{args.smtp_port}'
    )

    # initialize and start web server
    app = http.setup(args, args.http_auth)

    runner = aiohttp.web.AppRunner(app)
    loop.run_until_complete(runner.setup())

    site = aiohttp.web.TCPSite(runner, host=args.http_ip, port=args.http_port)
    server = site.start()
    loop.run_until_complete(server)

    logger.get().msg('http server started',
        host=args.http_ip, port=args.http_port,
        url=f'http://{args.http_ip}:{args.http_port}',
        auth='enabled' if args.http_auth else 'disabled',
        password_file=str(args.http_auth.path) if args.http_auth else None,
    )

    # initialize and run websocket notifier
    notifier.setup(app['websockets'], app['debug'])
    loop.create_task(notifier.ping())
    loop.create_task(notifier.send_messages())
    logger.get().msg('notifier initialized')

    # prepare for clean terminate
    async def _initialize_aiohttp_services__stop():
        # print('initialize_aiohttp_services _stop')
        for ws in set(app['websockets']):
            await ws.close(code=aiohttp.WSCloseCode.GOING_AWAY, message='Server shutdown')
        await app.shutdown()

    SHUTDOWN.append(_initialize_aiohttp_services__stop())

    signals = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)
    for s in signals:
        loop.add_signal_handler(s, lambda s=s: asyncio.create_task(terminate_server(s, loop)))


def stop(pidfile: pathlib.Path) -> None:
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

    if args.version:
        print('Sendria %s' % __version__)
        sys.exit(0)

    # Do we just want to stop a running daemon?
    if args.stop:
        logger.get().msg('stopping Sendria',
            debug='enabled' if args.debug else 'disabled',
            pidfile=str(args.pidfile) if args.pidfile else None,
        )
        stop(args.pidfile)
        sys.exit(0)

    logger.get().msg('starting Sendria',
        debug='enabled' if args.debug else 'disabled',
        pidfile=str(args.pidfile) if args.pidfile else None,
        db=str(args.db),
        foreground='true' if args.foreground else 'false',
    )

    # Check if the static folder is writable
    if args.autobuild_assets and not os.access(STATIC_DIR, os.W_OK):
        exit_err('autobuilding assets requires write access to %s' % STATIC_DIR)

    if not args.autobuild_assets and (not ASSETS_DIR.exists() or not list(ASSETS_DIR.glob('*'))):
        exit_err('assets not found. Generate assets using: webassets -m sendria.build_assets build', 0)

    daemon_kw = {}

    if args.foreground:
        # Do not detach and keep std streams open
        daemon_kw.update({
            'detach_process': False,
            'stdin': sys.stdin,
            'stdout': sys.stdout,
            'stderr': sys.stderr,
        })

    if args.pidfile:
        if args.pidfile.exists():
            pid = read_pidfile(args.pidfile)
            if not pid_exists(pid):
                logger.get().msg('deleting obsolete PID file (process %s does not exist)' % pid, pid=pid)
                args.pidfile.unlink()
        daemon_kw['pidfile'] = TimeoutPIDLockFile(str(args.pidfile), 5)

    # Unload threading module to avoid error on exit (it's loaded by lockfile)
    if 'threading' in sys.modules:
        del sys.modules['threading']

    context = daemon.DaemonContext(**daemon_kw)
    with context:
        loop = asyncio.get_event_loop()

        run_sendria_servers(loop, args)

        loop.run_forever()

    logger.get().msg('stop signal received')
    loop.close()

    logger.get().msg('terminating')
    sys.exit(0)
