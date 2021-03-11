__all__ = ['setup', 'enqueue']

import asyncio
import json
import traceback
from contextlib import asynccontextmanager
from typing import Any, Optional, NoReturn

import aiohttp
from structlog import get_logger

from . import __version__

logger = get_logger()
WEBHOOK_METHOD: str = 'POST'
WEBHOOK_URL: Optional[str] = None
WEBHOOK_AUTH: Optional[str] = None
DEBUG = False
CallbackMessagesQueue: Optional[asyncio.Queue] = None


def setup(
    *,
    debug_mode: bool = False,
    callback_webhook_url: str = None,
    callback_webhook_method: str = None,
    callback_webhook_auth: str = None,
) -> bool:
    global WEBHOOK_URL, WEBHOOK_METHOD, WEBHOOK_AUTH, DEBUG, CallbackMessagesQueue

    DEBUG = debug_mode

    if not callback_webhook_url:
        if DEBUG:
            logger.debug('webhooks disabled')
        return False

    WEBHOOK_URL = callback_webhook_url

    if callback_webhook_method:
        WEBHOOK_METHOD = callback_webhook_method.upper()

    if callback_webhook_auth:
        WEBHOOK_AUTH = callback_webhook_auth.split(':', 1)

    CallbackMessagesQueue = asyncio.Queue()

    if DEBUG:
        logger.debug('webhooks enabled', method=WEBHOOK_METHOD, url=WEBHOOK_URL,
            auth='enabled' if WEBHOOK_AUTH else 'disabled')
    return True


def prepare_payload(data: dict) -> NoReturn:
    data['recipients_message_to'] = json.loads(data['recipients_message_to'])
    data['recipients_message_cc'] = json.loads(data['recipients_message_cc'])
    data['recipients_message_bcc'] = json.loads(data['recipients_message_bcc'])


@asynccontextmanager
async def get_session() -> aiohttp.ClientSession:
    auth = None
    if WEBHOOK_AUTH:
        auth = aiohttp.BasicAuth(*WEBHOOK_AUTH)

    headers = {
        'User-agent': f'Sendria/{__version__} (https://github.com/msztolcman/sendria)',
        'Content-type': 'application/javascript',
    }

    session = aiohttp.ClientSession(
        auth=auth,
        headers=headers,
        # TODO: extract connect and total to some kind of settings/cli params
        timeout=aiohttp.ClientTimeout(connect=5, total=30),
    )
    try:
        yield session
    finally:
        await session.close()


async def send_messages() -> NoReturn:
    while True:
        payload = await CallbackMessagesQueue.get()
        prepare_payload(payload)

        try:
            async with get_session() as session:
                async with session.request(WEBHOOK_METHOD, WEBHOOK_URL, json=payload) as rsp:
                    if rsp.status != 200:
                        logger.warning('webhook response error', message_id=payload['message_id'], status=rsp.status,
                            reason=rsp.reason, url=WEBHOOK_URL, method=WEBHOOK_METHOD)
                    elif DEBUG:
                        logger.debug('webhook sent', message_id=payload['message_id'], status=rsp.status,
                            reason=rsp.reason, url=WEBHOOK_URL, method=WEBHOOK_METHOD)
        except aiohttp.ClientError:
            logger.error('webhook client error', traceback=traceback.format_exc())

        CallbackMessagesQueue.task_done()


async def enqueue(msg: Any) -> NoReturn:
    if not WEBHOOK_URL:
        return

    CallbackMessagesQueue.put_nowait(msg)
