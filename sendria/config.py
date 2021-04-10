import argparse
import os
import pathlib
import pkgutil
import sys
import tempfile
from typing import Optional, NoReturn

import attr
import fileperms
import structlog
import toml
from passlib.apache import HtpasswdFile

from . import exit_err

CONFIG: Optional['Config'] = None

logger = structlog.get_logger()
ENV_SENDRIA_CONFIG_DIR = 'SENDRIA_CONFIG_DIR'
ENV_XDG_CONFIG_HOME = 'XDG_CONFIG_HOME'
XDG_CONFIG_HOME = pathlib.Path('.config')
CONFIG_DIRNAME = 'sendria'
CONFIG_DIR: Optional[pathlib.Path]
CONFIG_FILE: Optional[pathlib.Path]
ROOT_DIR = pathlib.Path(pkgutil.get_loader('sendria').get_filename()).parent
STATIC_DIR = ROOT_DIR / 'static'
TEMPLATES_DIR = ROOT_DIR / 'templates'
ASSETS_DIR = STATIC_DIR / 'assets'
STATIC_URL = '/static/'
DEFAULT_OPTIONS = {
    'smtp_ident': 'ESMTP Sendria (https://sendria.net)',
    'smtp_ip': '127.0.0.1',
    'smtp_port': 1025,
    'http_ip': '127.0.0.1',
    'http_port': 1080,
    'callback_webhook_method': 'POST',
    'log_file': 'sendria.log',
}


def _generate_paths() -> NoReturn:
    global CONFIG_DIR, CONFIG_FILE
    CONFIG_DIR = get_config_dir()
    CONFIG_FILE = CONFIG_DIR / 'config.toml'


def get_config_dir() -> pathlib.Path:
    env_config_dir = os.environ.get(ENV_SENDRIA_CONFIG_DIR)
    if env_config_dir:
        return pathlib.Path(env_config_dir)

    home_dir = pathlib.Path.home()

    xdg_config_home_dir = os.environ.get(
        ENV_XDG_CONFIG_HOME,
        home_dir / XDG_CONFIG_HOME,
    )
    return pathlib.Path(xdg_config_home_dir) / CONFIG_DIRNAME


_generate_paths()


def ensure_config_files() -> NoReturn:
    global CONFIG_DIR, CONFIG_FILE
    dir_perms = fileperms.Permissions()
    dir_perms.owner_read = True
    dir_perms.owner_write = True
    dir_perms.owner_exec = True

    if not CONFIG_DIR.exists():
        CONFIG_DIR.mkdir(mode=int(dir_perms), parents=True, exist_ok=True)

    if not CONFIG_FILE.is_file():
        save_toml_file(CONFIG_FILE, {'sendria': {}})


def save_toml_file(file: pathlib.Path, data: dict) -> NoReturn:
    file_perms = fileperms.Permissions()
    file_perms.owner_read = True
    file_perms.owner_write = True

    try:
        with tempfile.NamedTemporaryFile(mode='w', dir=file.parent, delete=False, prefix='tmp.', suffix='.toml') as fh:
            tmp_file = pathlib.Path(fh.name)
            toml.dump(data, fh)
    except Exception as exc:
        logger.error('cannot save config file', file=str(file), message=str(exc))
        return

    tmp_file.chmod(int(file_perms))

    bak_file = None
    if file.exists():
        bak_file = file.parent / (file.name + '.bak')
        try:
            file.rename(bak_file)
        except Exception as exc:
            logger.error('cannot create backup file', file=str(bak_file), message=str(exc))
            return

    try:
        tmp_file.rename(file)
    except Exception as exc:
        logger.error('cannot create new config file', bak_file=str(bak_file), new_config=str(tmp_file), message=str(exc))
        print(f"Below content should be saved in {file}:", file=sys.stderr)
        print(toml.dumps(data), file=sys.stderr)
        return


@attr.s(slots=True)
class Config:
    db: Optional[pathlib.Path] = attr.ib(init=False)
    smtp_ip: Optional[str] = attr.ib(init=False)
    smtp_port: Optional[int] = attr.ib(init=False)
    smtp_auth: Optional[HtpasswdFile] = attr.ib(init=False)
    smtp_ident: Optional[str] = attr.ib(init=False)
    http_ip: Optional[str] = attr.ib(init=False)
    http_port: Optional[int] = attr.ib(init=False)
    http_auth: Optional[HtpasswdFile] = attr.ib(init=False)
    foreground: Optional[bool] = attr.ib(init=False)
    autobuild_assets: Optional[bool] = attr.ib(init=False)
    no_quit: Optional[bool] = attr.ib(init=False)
    no_clear: Optional[bool] = attr.ib(init=False)
    pidfile: Optional[pathlib.Path] = attr.ib(init=False)
    template_header_name: Optional[str] = attr.ib(init=False)
    template_header_url: Optional[str] = attr.ib(init=False)
    callback_webhook_url: Optional[str] = attr.ib(init=False)
    callback_webhook_method: Optional[str] = attr.ib(init=False)
    callback_webhook_auth: Optional[str] = attr.ib(init=False)
    log_file: Optional[pathlib.Path] = attr.ib(init=False)
    debug: bool = attr.ib(init=False)


def setup(args: argparse.Namespace) -> NoReturn:
    global CONFIG, CONFIG_FILE
    CONFIG = Config()

    with CONFIG_FILE.open('r') as fh:
        cfg = toml.load(fh)['sendria']

    for key in attr.fields(Config):
        name = key.name
        value = getattr(args, name)
        if value is None:
            value = cfg.get(name)
        if value is None:
            value = DEFAULT_OPTIONS.get(name)

        if name in ('db', 'pidfile') and isinstance(value, str):
            value = pathlib.Path(value)
            if not value.is_absolute():
                value = value.resolve()
        elif name in ('smtp_auth', 'http_auth') and isinstance(value, str):
            value = pathlib.Path(value)
            if not value.is_absolute():
                value = value.resolve()
            if value.is_file():
                value = HtpasswdFile(value)

        setattr(CONFIG, name, value)

    # Default to foreground mode if no pid file is specified
    if not CONFIG.pidfile and not CONFIG.foreground:
        logger.info('no PID file specified; runnning in foreground')
        CONFIG.foreground = True

    # Warn about relative paths and absolutize them
    if CONFIG.http_auth and not isinstance(CONFIG.http_auth, HtpasswdFile):
        exit_err('HTTP auth htpasswd file does not exist')

    if CONFIG.smtp_auth and not isinstance(CONFIG.smtp_auth, HtpasswdFile):
        exit_err('SMTP auth htpasswd file does not exist')

    if CONFIG.debug is None:
        CONFIG.debug = False
