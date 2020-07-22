import aiohttp.web

_webapp = None


def set_webapp(app: aiohttp.web.Application) -> None:
    global _webapp
    _webapp = app


async def broadcast(*args) -> None:
    for ws in set(_webapp['websockets']):
        await ws.send_str(','.join(map(str, args)))
