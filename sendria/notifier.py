import asyncio
import weakref
from typing import Optional, NoReturn

import aiohttp.web

from . import logger

DEBUG: bool = False

WSHandlers: Optional[weakref.WeakSet] = None
WebsocketMessages: Optional[asyncio.Queue] = None


def setup(websockets, debug) -> NoReturn:
    global WSHandlers, WebsocketMessages, DEBUG

    DEBUG = debug
    WSHandlers = websockets
    WebsocketMessages = asyncio.Queue()


async def ping() -> NoReturn:
    while True:
        ws: aiohttp.web.WebSocketResponse
        for ws in WSHandlers:
            await ws.ping()
        await asyncio.sleep(30)


async def broadcast(*args) -> NoReturn:
    WebsocketMessages.put_nowait(args)


async def send_messages() -> NoReturn:
    while True:
        msg = await WebsocketMessages.get()
        msg = ','.join(map(str, msg))

        cnt = 0
        ws: aiohttp.web.WebSocketResponse
        for ws in set(WSHandlers):
            await ws.send_str(msg)
            cnt += 1

        WebsocketMessages.task_done()

        if DEBUG:
            logger.get().msg('websocket messages sent', message=msg, receivers_cnt=cnt)
