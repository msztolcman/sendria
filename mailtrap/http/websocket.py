import asyncio
from typing import Optional

import aiohttp.web

from .. import logger

DEBUG: Optional[bool] = False
WEBAPP = None

WebsocketMessages: Optional[asyncio.Queue] = None


def setup(app: aiohttp.web.Application) -> None:
    global WEBAPP, WebsocketMessages, DEBUG
    WEBAPP = app
    DEBUG = app['debug']

    WebsocketMessages = asyncio.Queue()


async def ping():
    while True:
        ws: aiohttp.web.WebSocketResponse
        for ws in WEBAPP['websockets']:
            await ws.ping()
        await asyncio.sleep(30)


async def broadcast(*args) -> None:
    WebsocketMessages.put_nowait(args)


async def send_messages():
    while True:
        msg = await WebsocketMessages.get()

        ws: aiohttp.web.WebSocketResponse
        for ws in set(WEBAPP['websockets']):
            data = ','.join(map(str, msg))
            await ws.send_str(data)
            if DEBUG:
                logger.get().msg('websocket message sent', message=data)
        WebsocketMessages.task_done()
