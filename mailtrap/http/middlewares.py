import traceback

import aiohttp.web
from aiohttp_basicauth import BasicAuthMiddleware

from .. import errors
from .. import logger
from .. import __version__
from .json_encoder import json_response


@aiohttp.web.middleware
async def error_handler(rq: aiohttp.web.Request, handler) -> aiohttp.web.StreamResponse:
    try:
        rsp = await handler(rq)
    except errors.MailtrapException as exp:
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
        logger.get().msg('unauthorized access', uri=rq.url.human_repr(), header=header)
        raise
    except Exception:
        logger.get().msg('exception', exc_info=traceback.format_exc())
        raise
    return rsp


@aiohttp.web.middleware
async def response_from_dict(rq, handler) -> aiohttp.web.StreamResponse:
    rsp = await handler(rq)

    if isinstance(rsp, aiohttp.web.StreamResponse):
        return rsp

    if not rsp or 'code' not in rsp:
        ret = {
            'code': 'OK',
        }

        if rsp:
            ret['data'] = rsp

        rsp = ret

    return json_response(rsp)


@aiohttp.web.middleware
async def set_default_headers(rq, handler) -> aiohttp.web.StreamResponse:
    rsp = await handler(rq)
    rsp.headers['Server'] = f'MailTrap/{__version__} (https://github.com/msztolcman/mailtrap)'
    return rsp


class BasicAuth(BasicAuthMiddleware):
    def __init__(self, http_auth, *args, **kwargs):
        self._http_auth = http_auth
        kwargs['realm'] = 'MailTrap'
        kwargs['force'] = False
        super().__init__(*args, **kwargs)

    async def authenticate(self, rq):
        if not self._http_auth:
            return True

        res = await super().authenticate(rq)
        if not res:
            logger.get().msg(
                'request authentication failed',
                uri=rq.url.human_repr(),
                header=rq.headers.get('authorization', None)
            )

        return res

    async def check_credentials(self, username, password, rq):
        if self._http_auth.check_password(username, password):
            if rq.app['debug']:
                logger.get().msg('request authenticated', uri=rq.url.human_repr(), username=username)
            return True

        return False
