import asyncio
import json
from contextlib import asynccontextmanager
import traceback
from typing import Union

import aiohttp

from . import __version__
from . import logger

HTTP_URL: Union[str, None] = None
HTTP_METHOD: str = 'POST'
HTTP_AUTH: Union[str, None] = None
DEBUG = False
WebhookTasks: Optional[asyncio.Queue] = None


def setup(args):
    global HTTP_URL, HTTP_METHOD, HTTP_AUTH, DEBUG, WebhookTasks

    DEBUG = args.debug

    if not args.webhook_http_url:
        if DEBUG:
            logger.get().msg('webhooks disabled')
        return

    HTTP_URL = args.webhook_http_url

    if args.webhook_http_method:
        HTTP_METHOD = args.webhook_http_method

    if args.webhook_http_auth:
        HTTP_AUTH = args.webhook_http_auth.split(':', 1)

    WebhookTasks = asyncio.Queue()

    if DEBUG:
        logger.get().msg('INIT: webhooks enabled', method=HTTP_METHOD, url=HTTP_URL,
            auth='enabled' if HTTP_AUTH else 'disabled')


def build_payload(data):
    data['recipients_message_to'] = json.loads(data['recipients_message_to'])
    data['recipients_message_cc'] = json.loads(data['recipients_message_cc'])
    data['recipients_message_bcc'] = json.loads(data['recipients_message_bcc'])
    return data


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
        'timeout': aiohttp.ClientTimeout(connect=5, total=60),
    }

    session = aiohttp.ClientSession(**session_kwargs)
    yield session
    await session.close()


async def send_messages():
    while True:
        msg = await WebhookTasks.get()

        payload = build_payload(msg)

        try:
            async with get_session() as session:
                async with session.request(HTTP_METHOD, HTTP_URL, json=payload) as rsp:
                    if DEBUG:
                        logger.get().msg('webhook sent', message_id=msg['message_id'], status=rsp.status,
                                         reason=rsp.reason, url=HTTP_URL)
        except aiohttp.ClientError:
            logger.get().msg('webhook failed', traceback=traceback.format_exc())
            raise
        WebhookTasks.task_done()

        await asyncio.sleep(0.5)



async def execute(msg):
    if not HTTP_URL:
        return

    WebhookTasks.put_nowait(msg)
