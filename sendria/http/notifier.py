import asyncio
import weakref
from typing import Optional, NoReturn

import aiohttp.web
from structlog import get_logger

logger = get_logger()
DEBUG: bool = False
WSHandlers: Optional[weakref.WeakSet] = None
WebsocketMessagesQueue: Optional[asyncio.Queue] = None


def setup(*,
    websockets: weakref.WeakSet,
    debug_mode: bool,
) -> NoReturn:
    global WSHandlers, WebsocketMessagesQueue, DEBUG

    DEBUG = debug_mode
    WSHandlers = websockets
    WebsocketMessagesQueue = asyncio.Queue()


async def ping() -> NoReturn:
    while True:
        ws: aiohttp.web.WebSocketResponse
        for ws in WSHandlers:
            await ws.ping()
        await asyncio.sleep(30)


async def broadcast(*args) -> NoReturn:
    WebsocketMessagesQueue.put_nowait(args)


async def send_messages() -> NoReturn:
    while True:
        msg = await WebsocketMessagesQueue.get()
        msg = ','.join(map(str, msg))

        cnt = 0
        ws: aiohttp.web.WebSocketResponse
        for ws in set(WSHandlers):
            await ws.send_str(msg)
            cnt += 1

        WebsocketMessagesQueue.task_done()

        if DEBUG:
            logger.debug('websocket messages sent', message=msg, receivers_cnt=cnt)
