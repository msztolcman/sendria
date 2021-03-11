__all__ = []

import traceback
from typing import Callable

import aiohttp.web
from aiohttp_basicauth import BasicAuthMiddleware
from passlib.apache import HtpasswdFile
from structlog import get_logger

from .json_encoder import json_response
from .. import __version__
from .. import errors

logger = get_logger()


@aiohttp.web.middleware
async def error_handler(rq: aiohttp.web.Request, handler: Callable) -> aiohttp.web.StreamResponse:
    try:
        rsp = await handler(rq)
    except errors.SendriaException as exp:
        ret = {
            'code': exp.get_response_code(),
        }
        msg = exp.get_message()
        if msg:
            ret['message'] = msg
        return json_response(ret)
    except (aiohttp.web.HTTPNotFound, aiohttp.web.HTTPFound):
        raise
    except (aiohttp.web.HTTPForbidden, aiohttp.web.HTTPUnauthorized):
        header = rq.headers.get('authorization', None)
        logger.debug('unauthorized access', uri=rq.url.human_repr(), header=header)
        raise
    except Exception:
        logger.exception('exception', exc_info=traceback.format_exc())
        raise
    return rsp


@aiohttp.web.middleware
async def response_from_dict(rq: aiohttp.web.Request, handler: Callable) -> aiohttp.web.StreamResponse:
    rsp = await handler(rq)

    if isinstance(rsp, aiohttp.web.StreamResponse):
        return rsp

    if not rsp or 'code' not in rsp:
        ret = {
            'code': 'OK',
        }

        if rsp is not None:
            ret['data'] = rsp

        rsp = ret

    return json_response(rsp)


@aiohttp.web.middleware
async def set_default_headers(rq: aiohttp.web.Request, handler: Callable) -> aiohttp.web.StreamResponse:
    rsp = await handler(rq)
    rsp.headers['Server'] = f'Sendria/{__version__} (https://github.com/msztolcman/sendria)'
    return rsp


class BasicAuth(BasicAuthMiddleware):
    def __init__(self, http_auth: HtpasswdFile, *args, **kwargs):
        self._http_auth = http_auth
        kwargs['realm'] = 'Sendria'
        kwargs['force'] = False
        super().__init__(*args, **kwargs)

    async def authenticate(self, rq: aiohttp.web.Request) -> bool:
        if not self._http_auth:
            return True

        res = await super().authenticate(rq)
        if not res:
            logger.info(
                'request authentication failed',
                uri=rq.url.human_repr(),
                header=rq.headers.get('authorization', None)
            )

        return res

    async def check_credentials(self, username: str, password: str, rq: aiohttp.web.Request) -> bool:
        if self._http_auth.check_password(username, password):
            if rq.app['debug']:
                logger.debug('request authenticated', uri=rq.url.human_repr(), username=username)
            return True

        return False
