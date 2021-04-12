__all__ = ['main', 'terminate_server']

import argparse
import asyncio
import errno
import os
import pathlib
import signal
import sys
from typing import NoReturn, List, IO

import aiohttp.web
import daemon
import structlog
from daemon.pidfile import TimeoutPIDLockFile
from structlog import get_logger

from . import __version__, exit_err
from . import callback
from . import config
from . import db
from . import http
from . import smtp

logger = get_logger()
SHUTDOWN = []


def parse_argv(argv: List) -> argparse.Namespace:
    parser = argparse.ArgumentParser('Sendria')
    version = f'%(prog)s {__version__} (https://sendria.net (c) 2018 Marcin Sztolcman)'
    parser.add_argument('-v', '--version', action='version', version=version,
        help='Display the version and exit')

    parser.add_argument('-s', '--db', metavar='PATH', help='Path to SQLite database. Will be created if doesn\'t exist')
    parser.add_argument('--smtp-ip', metavar='IP', help='SMTP ip (default: 127.0.0.1)')
    parser.add_argument('--smtp-port', type=int, metavar='PORT', help='SMTP port (default: 1025)')
    parser.add_argument('--smtp-auth', metavar='HTPASSWD',
        help='Apache-style htpasswd file for SMTP authorization. '
            'WARNING: do not rely only on this as a security '
            'mechanism, use also additional methods for securing '
            'Sendria instance, ie. IP restrictions.')
    parser.add_argument('--smtp-ident',
        help='How SMTP server will identify when connect')
    parser.add_argument('--http-ip', metavar='IP', help='HTTP ip (default: 127.0.0.1)')
    parser.add_argument('--http-port', type=int, metavar='PORT', help='HTTP port (default: 1080)')
    parser.add_argument('--http-auth', metavar='HTPASSWD', help='Apache-style htpasswd file')
    parser.add_argument('--http-url-prefix',
        help='')
    parser.add_argument('-f', '--foreground', action='store_true', default=None,
        help='Run in the foreground (default if no pid file is specified)')
    parser.add_argument('-d', '--debug', help='Run the web app in debug mode', action='store_true', default=None)
    parser.add_argument('-a', '--autobuild-assets', action='store_true', default=None,
        help='Automatically rebuild assets if necessary')
    parser.add_argument('-n', '--no-quit', action='store_true', default=None,
        help='Do not allow clients to terminate the application')
    parser.add_argument('-c', '--no-clear', action='store_true', default=None,
        help='Do not allow clients to clear email database')
    parser.add_argument('-p', '--pidfile', help='Use a PID file')
    parser.add_argument('--stop', action='store_true',
        help='Sends SIGTERM to the running daemon (needs --pidfile)')
    parser.add_argument('--template-header-name', help='Additional name of application')
    parser.add_argument('--template-header-url', help='Url of application')
    parser.add_argument('--callback-webhook-url',
        help='URL where webhook shoud be sent. If empty (default) then no webhook is sent.')
    parser.add_argument('--callback-webhook-method',
        help='HTTP method for webhook')
    parser.add_argument('--callback-webhook-auth',
        help='Optional credentials ("login:password") for webhook (only Basic Auth supported). If empty, then no '
            'authorization header is sent')
    parser.add_argument('--log-file',
        help='Where logs have to come if working in background. Ignored if working in foreground.')
    parser.add_argument('--config-file', '-g',
        help=f'configuration file to use (default: {config.CONFIG_FILE})')

    args = parser.parse_args(argv)

    if args.stop:
        return args

    return args


def configure_logger() -> IO:
    if config.CONFIG.foreground or not config.CONFIG.pidfile or config.CONFIG.log_file == '-':
        processors = (
            structlog.dev.ConsoleRenderer(),
        )
        log_handler = sys.stdout
    else:
        processors = (
            structlog.processors.JSONRenderer(),
        )
        log_handler = open(config.CONFIG.log_file, 'a')

    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.format_exc_info,
            structlog.processors.TimeStamper("ISO"),
            *processors,
        ],
        wrapper_class=structlog.BoundLogger,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=log_handler),
        cache_logger_on_first_use=True,
    )

    return log_handler


def pid_exists(pid: int) -> bool:
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
        raise ValueError(str(exc))


async def terminate_server(sig: int, loop: asyncio.AbstractEventLoop) -> NoReturn:
    if sig == signal.SIGINT and os.isatty(sys.stdout.fileno()):
        # Terminate the line containing ^C
        print()

    await asyncio.gather(*SHUTDOWN, return_exceptions=True)

    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)

    loop.stop()


def run_sendria_servers(loop: asyncio.AbstractEventLoop) -> NoReturn:
    # initialize db
    loop.run_until_complete(db.setup(config.CONFIG.db))

    # initialize and start webhooks
    callbacks_enabled = callback.setup(
        debug_mode=config.CONFIG.debug,
        callback_webhook_url=config.CONFIG.callback_webhook_url,
        callback_webhook_method=config.CONFIG.callback_webhook_method,
        callback_webhook_auth=config.CONFIG.callback_webhook_auth,
    )
    if callbacks_enabled:
        loop.create_task(callback.send_messages())

    # initialize and start message saver
    loop.create_task(db.message_saver())

    # start smtp server
    smtp.run(config.CONFIG.smtp_ip, config.CONFIG.smtp_port, config.CONFIG.smtp_auth, config.CONFIG.smtp_ident, config.CONFIG.debug)
    logger.info('smtp server started', host=config.CONFIG.smtp_ip, port=config.CONFIG.smtp_port,
        auth='enabled' if config.CONFIG.smtp_auth else 'disabled',
        password_file=str(config.CONFIG.smtp_auth.path) if config.CONFIG.smtp_auth else None,
        url=f'smtp://{config.CONFIG.smtp_ip}:{config.CONFIG.smtp_port}',
    )

    # initialize and start web server
    app = http.setup()

    runner = aiohttp.web.AppRunner(app)
    loop.run_until_complete(runner.setup())

    site = aiohttp.web.TCPSite(runner, host=config.CONFIG.http_ip, port=config.CONFIG.http_port)
    server = site.start()
    loop.run_until_complete(server)

    logger.info('http server started',
        host=config.CONFIG.http_ip, port=config.CONFIG.http_port,
        url=f'http://{config.CONFIG.http_ip}:{config.CONFIG.http_port}',
        auth='enabled' if config.CONFIG.http_auth else 'disabled',
        password_file=str(config.CONFIG.http_auth.path) if config.CONFIG.http_auth else None,
    )

    # prepare for clean terminate
    async def _initialize_aiohttp_services__stop() -> NoReturn:
        for ws in set(app['websockets']):
            await ws.close(code=aiohttp.WSCloseCode.GOING_AWAY, message='Server shutdown')
        await app.shutdown()

    SHUTDOWN.append(_initialize_aiohttp_services__stop())

    signals = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)
    for s in signals:
        loop.add_signal_handler(s, lambda s=s: asyncio.create_task(terminate_server(s, loop)))


def stop(pidfile: pathlib.Path) -> NoReturn:
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


def main() -> NoReturn:
    config.ensure_config_files()
    args = parse_argv(sys.argv[1:])
    config.setup(args)

    if not config.CONFIG.db:
        exit_err('Missing database path. Please use --db path/to/db.sqlite')

    log_handler = configure_logger()

    # Do we just want to stop a running daemon?
    if args.stop:
        logger.info('stopping Sendria',
            debug='enabled' if config.CONFIG.debug else 'disabled',
            pidfile=str(config.CONFIG.pidfile) if config.CONFIG.pidfile else None,
        )
        stop(config.CONFIG.pidfile)
        sys.exit(0)

    logger.info('starting Sendria',
        debug='enabled' if config.CONFIG.debug else 'disabled',
        pidfile=str(config.CONFIG.pidfile) if config.CONFIG.pidfile else None,
        db=str(config.CONFIG.db),
        foreground='true' if config.CONFIG.foreground else 'false',
    )

    # Check if the static folder is writable
    if config.CONFIG.autobuild_assets and not os.access(config.STATIC_DIR, os.W_OK):
        exit_err('autobuilding assets requires write access to %s' % config.STATIC_DIR)

    if not config.CONFIG.autobuild_assets and (not config.ASSETS_DIR.exists() or not list(config.ASSETS_DIR.glob('*'))):
        exit_err('assets not found. Generate assets using: webassets -m sendria.build_assets build', 0)

    daemon_kw = {}

    if log_handler.name != '<stdout>':
        daemon_kw['files_preserve'] = [log_handler]

    if config.CONFIG.foreground:
        # Do not detach and keep std streams open
        daemon_kw.update({
            'detach_process': False,
            'stdin': sys.stdin,
            'stdout': sys.stdout,
            'stderr': sys.stderr,
        })

    if config.CONFIG.pidfile:
        if config.CONFIG.pidfile.exists():
            try:
                pid = read_pidfile(config.CONFIG.pidfile)
            except Exception as exc:
                exit_err(f'Cannot read pid file: {exc}', 1)

            if not pid_exists(pid):
                logger.warning('deleting obsolete PID file (process %s does not exist)' % pid, pid=pid)
                config.CONFIG.pidfile.unlink()
        daemon_kw['pidfile'] = TimeoutPIDLockFile(str(config.CONFIG.pidfile), 5)

    # Unload threading module to avoid error on exit (it's loaded by lockfile)
    if 'threading' in sys.modules:
        del sys.modules['threading']

    context = daemon.DaemonContext(**daemon_kw)
    with context:
        loop = asyncio.get_event_loop()

        run_sendria_servers(loop)

        loop.run_forever()

    logger.info('stop signal received')
    loop.close()

    logger.info('terminating')
    sys.exit(0)
