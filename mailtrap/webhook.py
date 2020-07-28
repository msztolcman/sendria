__all__ = ['setup', 'enqueue']

import argparse
import asyncio
import json
import traceback
from contextlib import asynccontextmanager
from typing import Any, Optional

import aiohttp

from . import __version__
from . import logger

HTTP_METHOD: str = 'POST'
HTTP_URL: Optional[str] = None
HTTP_AUTH: Optional[str] = None
DEBUG = False
Messages: Optional[asyncio.Queue] = None


def setup(args: argparse.Namespace) -> bool:
    global HTTP_URL, HTTP_METHOD, HTTP_AUTH, DEBUG, Messages

    DEBUG = args.debug

    if not args.webhook_http_url:
        if DEBUG:
            logger.get().msg('webhooks disabled')
        return False

    HTTP_URL = args.webhook_http_url

    if args.webhook_http_method:
        HTTP_METHOD = args.webhook_http_method

    if args.webhook_http_auth:
        HTTP_AUTH = args.webhook_http_auth.split(':', 1)

    Messages = asyncio.Queue()

    if DEBUG:
        logger.get().msg('webhooks enabled', method=HTTP_METHOD, url=HTTP_URL,
            auth='enabled' if HTTP_AUTH else 'disabled')
    return True


def prepare_payload(data: dict) -> None:
    data['recipients_message_to'] = json.loads(data['recipients_message_to'])
    data['recipients_message_cc'] = json.loads(data['recipients_message_cc'])
    data['recipients_message_bcc'] = json.loads(data['recipients_message_bcc'])


@asynccontextmanager
async def get_session() -> aiohttp.ClientSession:
    auth = None
    if HTTP_AUTH:
        auth = aiohttp.BasicAuth(*HTTP_AUTH)

    headers = {
        'User-agent': f'MailTrap/{__version__} (https://github.com/msztolcman/mailtrap)',
        'Content-type': 'application/javascript',
    }

    session_kwargs = {
        'auth': auth,
        'headers': headers,
        'timeout': aiohttp.ClientTimeout(connect=5, total=30),
    }

    session = aiohttp.ClientSession(**session_kwargs)
    try:
        yield session
    finally:
        await session.close()


async def send_messages() -> None:
    while True:
        payload = await Messages.get()
        prepare_payload(payload)

        try:
            async with get_session() as session:
                async with session.request(HTTP_METHOD, HTTP_URL, json=payload) as rsp:
                    if rsp.status != 200:
                        logger.get().msg('webhook response error', message_id=payload['message_id'], status=rsp.status,
                            reason=rsp.reason, url=HTTP_URL)
                    elif DEBUG:
                        logger.get().msg('webhook sent', message_id=payload['message_id'], status=rsp.status,
                            reason=rsp.reason, url=HTTP_URL)
        except aiohttp.ClientError:
            logger.get().msg('webhook client error', traceback=traceback.format_exc())

        Messages.task_done()


async def enqueue(msg: Any) -> None:
    if not HTTP_URL:
        return

    Messages.put_nowait(msg)
