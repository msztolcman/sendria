import asyncio

import aiohttp.web

_webapp = None

WebsocketMessages = asyncio.Queue()


def set_webapp(app: aiohttp.web.Application) -> None:
    global _webapp
    _webapp = app


async def broadcast(*args) -> None:
    WebsocketMessages.put_nowait(args)


async def send_messages():
    while True:
        msg = await WebsocketMessages.get()
        for ws in set(_webapp['websockets']):
            await ws.send_str(','.join(map(str, msg)))
        WebsocketMessages.task_done()

        await asyncio.sleep(0.5)
