import pathlib
from typing import Optional

import attr
from passlib.apache import HtpasswdFile

_CONFIG: Optional['Config'] = None


@attr.s(slots=True)
class Config:
    template_header_name: Optional[str] = None
    template_header_url: Optional[str] = None
    smtp_ip: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_auth: Optional[HtpasswdFile] = None
    http_ip: Optional[str] = None
    http_port: Optional[int] = None
    db: Optional[pathlib.Path] = None
    htpasswd: Optional[HtpasswdFile] = None
    foreground: Optional[bool] = None
    debug: bool = False
    autobuild_assets: Optional[bool] = None
    no_quit: Optional[bool] = None
    no_clear: Optional[bool] = None
    pidfile: Optional[pathlib.Path] = None
    webhook_http_url: Optional[str] = None
    webhook_http_method: Optional[str] = None
    webhook_http_auth: Optional[str] = None


def get(key: Optional[str] = None) -> Optional[Config]:
    if not key:
        return _CONFIG

    if not hasattr(_CONFIG, key):
        raise KeyError(f'Unknown key: {key}')

    return getattr(_CONFIG, key)


def setup(args):
    global _CONFIG

    _CONFIG = Config()
    for name in _CONFIG.__slots__:
        setattr(_CONFIG, name, getattr(args, name))
