__all__ = ['setup', 'configure_assets']

import argparse
import asyncio
import re
import weakref
from typing import Union, NoReturn, Optional

import aiohttp.web
import aiohttp_jinja2
import bs4
import jinja2
import webassets
import yarl
from passlib.apache import HtpasswdFile
from structlog import get_logger

from . import middlewares
from . import notifier
from .. import STATIC_DIR, STATIC_URL, TEMPLATES_DIR
from .. import __version__
from .. import db

logger = get_logger()
RE_CID = re.compile(r'(?P<replace>cid:(?P<cid>.+))')
RE_CID_URL = re.compile(r'url\(\s*(?P<quote>["\']?)(?P<replace>cid:(?P<cid>[^\\\')]+))(?P=quote)\s*\)')

WebHandlerResponse = Union[dict, list, str, int, aiohttp.web.StreamResponse, None]


@aiohttp_jinja2.template('index.html')
async def home(rq: aiohttp.web.Request) -> WebHandlerResponse:
    assets = rq.app['assets']
    return {
        'version': __version__,
        'sendria_no_quit': rq.app['SENDRIA_NO_QUIT'],
        'sendria_no_clear': rq.app['SENDRIA_NO_CLEAR'],
        'js_all': assets['js_all'].urls(),
        'css_all': assets['css_all'].urls(),
        'header_name': rq.app['HEADER_NAME'],
        'header_url': rq.app['HEADER_URL'],
    }


async def terminate(rq: aiohttp.web.Request) -> WebHandlerResponse:
    if rq.app['SENDRIA_NO_QUIT']:
        raise aiohttp.web.HTTPForbidden()

    logger.info('Terminate request received')
    import os
    import signal
    os.kill(os.getpid(), signal.SIGTERM)

    return


async def delete_messages(rq: aiohttp.web.Request) -> WebHandlerResponse:
    if rq.app['SENDRIA_NO_CLEAR']:
        raise aiohttp.web.HTTPForbidden()

    async with db.connection() as conn:
        await db.delete_messages(conn)

    return {}


async def get_messages(rq: aiohttp.web.Request) -> WebHandlerResponse:
    async with db.connection() as conn:
        messages = await db.get_messages(conn)
    return messages or []


async def delete_message(rq: aiohttp.web.Request) -> WebHandlerResponse:
    message_id = rq.match_info.get('message_id')
    async with db.connection() as conn:
        message = await db.get_message(conn, message_id)
        if not message:
            raise aiohttp.web.HTTPNotFound(text='404: message does not exist')
        await db.delete_message(conn, message_id)

    return {}


async def _part_url(rq: aiohttp.web.Request, part: dict) -> yarl.URL:
    return rq.app.router['get-message-part'].url_for(message_id=str(part['message_id']), cid=part['cid'])


async def _part_response(rq: aiohttp.web.Request, part: dict, body: Optional[Union[str, bytes]] = None,
    charset: Optional[str] = None,
) -> WebHandlerResponse:
    charset = charset or part['charset'] or 'utf-8'
    if body is None:
        body = part['body']
    if charset != 'utf-8':
        body = body.decode(charset).encode('utf-8')
    if isinstance(body, str):
        body = body.encode()

    response = aiohttp.web.StreamResponse()
    response.content_type = part['type']
    await response.prepare(rq)
    await response.write(body)
    await response.write_eof()
    return response


async def get_message_info(rq: aiohttp.web.Request) -> WebHandlerResponse:
    message_id = rq.match_info.get('message_id')
    async with db.connection() as conn:
        message = await db.get_message(conn, message_id)
        if not message:
            raise aiohttp.web.HTTPNotFound(text='404: message does not exist')
        message['href'] = rq.app.router['get-message-eml'].url_for(message_id=message_id)
        message['formats'] = {'source': rq.app.router['get-message-source'].url_for(message_id=message_id)}
        if await db.message_has_plain(conn, message_id):
            message['formats']['plain'] = rq.app.router['get-message-plain'].url_for(message_id=message_id)
        if await db.message_has_html(conn, message_id):
            message['formats']['html'] = rq.app.router['get-message-html'].url_for(message_id=message_id)
        message['attachments'] = [dict(part, href=await _part_url(rq, part)) for part in await db.get_message_attachments(conn, message_id)]
    return message or {}


async def get_message_plain(rq: aiohttp.web.Request) -> WebHandlerResponse:
    message_id = rq.match_info.get('message_id')
    async with db.connection() as conn:
        part = await db.get_message_part_plain(conn, message_id)
    if not part:
        raise aiohttp.web.HTTPNotFound(text='404: part does not exist')
    return await _part_response(rq, part) or {}


async def _fix_cid_links(rq: aiohttp.web.Request, soup: bs4.BeautifulSoup, message_id: Union[str, bytes]) -> NoReturn:
    def _url_from_cid_match(m: re.Match) -> str:
        url = rq.app.router['get-message-part'].url_for(message_id=str(message_id), cid=m.group('cid'))
        return m.group().replace(m.group('replace'), str(url))

    # Iterate over all attributes that do not contain CSS and replace cid references
    # for tag in (x for x in soup.descendants if isinstance(x, bs4.Tag)):
    for tag in soup.descendants:
        if not isinstance(tag, bs4.Tag):
            continue
        for name, value in tag.attrs.items():
            if isinstance(value, list):
                value = ' '.join(value)
            m = RE_CID.match(value)
            if m is not None:
                tag.attrs[name] = _url_from_cid_match(m)
    # Rewrite cid references within inline stylesheets
    for tag in soup.find_all('style'):
        tag.string = RE_CID_URL.sub(_url_from_cid_match, tag.string)


def _links_target_blank(soup: bs4.BeautifulSoup) -> NoReturn:
    for tag in soup.descendants:
        if isinstance(tag, bs4.Tag) and tag.name == 'a':
            tag.attrs['target'] = 'blank'


async def get_message_html(rq: aiohttp.web.Request) -> WebHandlerResponse:
    message_id = rq.match_info.get('message_id')
    async with db.connection() as conn:
        part = await db.get_message_part_html(conn, message_id)
    if not part:
        raise aiohttp.web.HTTPNotFound(text='404: part does not exist')
    charset = part['charset'] or 'utf-8'
    soup = bs4.BeautifulSoup(part['body'].decode(charset, 'ignore'), 'html5lib')
    await _fix_cid_links(rq, soup, message_id)
    _links_target_blank(soup)
    return await _part_response(rq, part, str(soup), 'utf-8') or {}


async def get_message_source(rq: aiohttp.web.Request) -> WebHandlerResponse:
    message_id = rq.match_info.get('message_id')
    async with db.connection() as conn:
        message = await db.get_message(conn, message_id)
    if not message:
        raise aiohttp.web.HTTPNotFound(text='404: message does not exist')

    response = aiohttp.web.StreamResponse()
    response.content_type = 'text/plain'
    await response.prepare(rq)
    await response.write(message['source'].encode('utf-8', 'ignore'))
    await response.write_eof()

    return response or {}


async def get_message_eml(rq: aiohttp.web.Request) -> WebHandlerResponse:
    message_id = rq.match_info.get('message_id')
    async with db.connection() as conn:
        message = await db.get_message(conn, message_id)
    if not message:
        raise aiohttp.web.HTTPNotFound(text='404: message does not exist')

    response = aiohttp.web.StreamResponse()
    response.content_type = 'message/rfc822'
    await response.prepare(rq)
    await response.write(message['source'].encode('utf-8', 'ignore'))
    await response.write_eof()

    return response or {}


async def get_message_part(rq: aiohttp.web.Request) -> WebHandlerResponse:
    message_id = rq.match_info.get('message_id')
    cid = rq.match_info.get('cid')
    async with db.connection() as conn:
        part = await db.get_message_part_cid(conn, message_id, cid)
    if not part:
        raise aiohttp.web.HTTPNotFound(text='404: part does not exist')
    return await _part_response(rq, part) or {}


async def websocket_handler(rq: aiohttp.web.Request) -> aiohttp.web.WebSocketResponse:
    ws = aiohttp.web.WebSocketResponse()
    await ws.prepare(rq)

    if rq.app['debug']:
        logger.debug('websocket connection opened', peer=rq.remote)

    rq.app['websockets'].add(ws)
    try:
        async for ws_message in ws:
            if ws_message.type == aiohttp.WSMsgType.ERROR:
                logger.warning('ws connection closed with error', exception=ws.exception(), peer=rq.remote)
    finally:
        rq.app['websockets'].discard(ws)

    if rq.app['debug']:
        logger.debug('websocket connection closed', peer=rq.remote)

    return ws


def configure_assets(debug: bool, autobuild: bool) -> webassets.Environment:
    js = webassets.Bundle('js/lib/jquery.js', 'js/lib/jquery-ui.js', 'js/lib/jquery.hotkeys.js',
        'js/lib/handlebars.js', 'js/lib/moment.js', 'js/lib/jstorage.js',
        'js/util.js', 'js/message.js', 'js/sendria.js',
        filters='rjsmin', output='assets/bundle.%(version)s.js')
    scss = webassets.Bundle('css/sendria.scss',
        filters='pyscss', output='assets/sendria.%(version)s.css')
    css = webassets.Bundle('css/reset.css', 'css/jquery-ui.css', scss,
        filters=('cssrewrite', 'cssmin'), output='assets/bundle.%(version)s.css')

    assets = webassets.Environment(directory=STATIC_DIR, url=STATIC_URL)
    assets.debug = debug  # yuck! but the commandline script only supports *disabling* debug
    assets.auto_build = autobuild

    assets.register('js_all', js)
    assets.register('css_all', css)

    return assets


def setup(args: argparse.Namespace, http_auth: HtpasswdFile) -> aiohttp.web.Application:
    app = aiohttp.web.Application(debug=args.debug)
    app.middlewares.extend([
        middlewares.set_default_headers,
        middlewares.error_handler,
        middlewares.response_from_dict,
    ])

    app['SENDRIA_NO_QUIT'] = args.no_quit
    app['SENDRIA_NO_CLEAR'] = args.no_clear
    app['HEADER_NAME'] = args.template_header_name
    app['HEADER_URL'] = args.template_header_url
    app['debug'] = args.debug
    app['websockets'] = weakref.WeakSet()

    assets = configure_assets(args.debug, args.autobuild_assets)
    app['assets'] = assets

    # aiohttp_jinja requirement
    app['static_root_url'] = STATIC_URL
    aiohttp_jinja2.setup(app, loader=jinja2.FileSystemLoader(TEMPLATES_DIR))

    auth = middlewares.BasicAuth(http_auth)
    app.add_routes([
        aiohttp.web.get('/', home, name='home'),
        aiohttp.web.delete('/api', auth.required(terminate), name='terminate'),
        aiohttp.web.delete('/api/messages/', auth.required(delete_messages), name='delete-messages'),
        aiohttp.web.get('/api/messages/', auth.required(get_messages), name='get-messages'),
        aiohttp.web.delete(r'/api/messages/{message_id:\d+}', auth.required(delete_message), name='delete-message'),
        aiohttp.web.get(r'/api/messages/{message_id:\d+}.json', auth.required(get_message_info), name='get-message-info'),
        aiohttp.web.get(r'/api/messages/{message_id:\d+}.plain', auth.required(get_message_plain), name='get-message-plain'),
        aiohttp.web.get(r'/api/messages/{message_id:\d+}.html', auth.required(get_message_html), name='get-message-html'),
        aiohttp.web.get(r'/api/messages/{message_id:\d+}.source', auth.required(get_message_source), name='get-message-source'),
        aiohttp.web.get(r'/api/messages/{message_id:\d+}.eml', auth.required(get_message_eml), name='get-message-eml'),
        aiohttp.web.get(r'/api/messages/{message_id:\d+}/parts/{cid}', auth.required(get_message_part), name='get-message-part'),

        aiohttp.web.get(r'/ws', websocket_handler),
    ])
    app.router.add_static('/static/', path=STATIC_DIR, name='static')

    # initialize and run websocket notifier
    notifier.setup(websockets=app['websockets'], debug_mode=app['debug'])
    loop = asyncio.get_event_loop()
    loop.create_task(notifier.ping())
    loop.create_task(notifier.send_messages())
    logger.info('notifier initialized')

    return app
