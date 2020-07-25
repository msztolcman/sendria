import re
import weakref

import aiohttp.web
import aiohttp_jinja2
import bs4
import jinja2
import webassets

from .. import STATIC_DIR, STATIC_URL, TEMPLATES_DIR
from .. import db
from .. import logger
from .. import __version__
from . import middlewares
from . import websocket

RE_CID = re.compile(r'(?P<replace>cid:(?P<cid>.+))')
RE_CID_URL = re.compile(r'url\(\s*(?P<quote>["\']?)(?P<replace>cid:(?P<cid>[^\\\')]+))(?P=quote)\s*\)')


@aiohttp_jinja2.template('index.html')
async def home(rq):
    assets = rq.app['assets']
    return {
        'version': __version__,
        'mailtrap_no_quit': rq.app['MAILTRAP_NO_QUIT'],
        'mailtrap_no_clear': rq.app['MAILTRAP_NO_CLEAR'],
        'js_all': assets['js_all'].urls(),
        'css_all': assets['css_all'].urls(),
        'header_name': rq.app['HEADER_NAME'],
        'header_url': rq.app['HEADER_URL'],
    }


async def terminate(rq):
    if rq.app['MAILTRAP_NO_QUIT']:
        raise aiohttp.web.HTTPForbidden()

    logger.get().msg('Terminate request received')
    import os
    import signal
    os.kill(os.getpid(), signal.SIGTERM)


async def delete_messages(rq):
    if rq.app['MAILTRAP_NO_CLEAR']:
        raise aiohttp.web.HTTPForbidden()

    async with db.connection() as conn:
        await db.delete_messages(conn)


async def get_messages(rq):
    async with db.connection() as conn:
        messages = await db.get_messages(conn)
    return messages


async def delete_message(rq):
    message_id = rq.match_info.get('message_id')
    async with db.connection() as conn:
        message = await db.get_message(conn, message_id)
        if not message:
            raise aiohttp.web.HTTPNotFound(text='404: message does not exist')
        await db.delete_message(conn, message_id)


async def _part_url(rq, part):
    return rq.app.router['get-message-part'].url_for(message_id=str(part['message_id']), cid=part['cid'])


async def _part_response(rq, part, body=None, charset=None):
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


async def get_message_info(rq):
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
    return message


async def get_message_plain(rq):
    message_id = rq.match_info.get('message_id')
    async with db.connection() as conn:
        part = await db.get_message_part_plain(conn, message_id)
    if not part:
        raise aiohttp.web.HTTPNotFound(text='404: part does not exist')
    return await _part_response(rq, part)


async def _fix_cid_links(rq, soup, message_id):
    def _url_from_cid_match(m):
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


def _links_target_blank(soup):
    for tag in soup.descendants:
        if isinstance(tag, bs4.Tag) and tag.name == 'a':
            tag.attrs['target'] = 'blank'


async def get_message_html(rq):
    message_id = rq.match_info.get('message_id')
    async with db.connection() as conn:
        part = await db.get_message_part_html(conn, message_id)
    if not part:
        raise aiohttp.web.HTTPNotFound(text='404: part does not exist')
    charset = part['charset'] or 'utf-8'
    soup = bs4.BeautifulSoup(part['body'].decode(charset, 'ignore'), 'html5lib')
    await _fix_cid_links(rq, soup, message_id)
    _links_target_blank(soup)
    return await _part_response(rq, part, str(soup), 'utf-8')


async def get_message_source(rq):
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

    return response


async def get_message_eml(rq):
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

    return response


async def get_message_part(rq):
    message_id = rq.match_info.get('message_id')
    cid = rq.match_info.get('cid')
    async with db.connection() as conn:
        part = await db.get_message_part_cid(conn, message_id, cid)
    if not part:
        raise aiohttp.web.HTTPNotFound(text='404: part does not exist')
    return await _part_response(rq, part)


async def websocket_handler(rq: aiohttp.web.Request):
    ws = aiohttp.web.WebSocketResponse()
    await ws.prepare(rq)

    if rq.app['debug']:
        logger.get().msg('websocket connection opened', peer=rq.remote)

    rq.app['websockets'].add(ws)
    try:
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.ERROR:
                logger.get().msg('ws connection closed with exception ', exception=ws.exception(), peer=rq.remote)
    finally:
        rq.app['websockets'].discard(ws)

    if rq.app['debug']:
        logger.get().msg('websocket connection closed', peer=rq.remote)

    return ws


def configure_assets(debug: bool, autobuild: bool) -> webassets.Environment:
    js = webassets.Bundle('js/lib/jquery.js', 'js/lib/jquery-ui.js', 'js/lib/jquery.hotkeys.js',
        'js/lib/handlebars.js', 'js/lib/moment.js', 'js/lib/jstorage.js',
        'js/util.js', 'js/message.js', 'js/mailtrap.js',
        filters='rjsmin', output='assets/bundle.%(version)s.js')
    scss = webassets.Bundle('css/mailtrap.scss',
        filters='pyscss', output='assets/mailtrap.%(version)s.css')
    css = webassets.Bundle('css/reset.css', 'css/jquery-ui.css', scss,
        filters=('cssrewrite', 'cssmin'), output='assets/bundle.%(version)s.css')

    assets = webassets.Environment(directory=STATIC_DIR, url=STATIC_URL)
    assets.debug = debug  # yuck! but the commandline script only supports *disabling* debug
    assets.auto_build = autobuild

    assets.register('js_all', js)
    assets.register('css_all', css)

    return assets


def setup(args, http_auth):
    app = aiohttp.web.Application(debug=args.debug)
    app.middlewares.append(middlewares.set_default_headers)
    app.middlewares.append(middlewares.error_handler)
    app.middlewares.append(middlewares.response_from_dict)

    aiohttp_jinja2.setup(app, loader=jinja2.FileSystemLoader(TEMPLATES_DIR))

    websocket.set_webapp(app)

    assets = configure_assets(args.debug, args.autobuild_assets)
    app['assets'] = assets
    app['MAILTRAP_NO_QUIT'] = args.no_quit
    app['MAILTRAP_NO_CLEAR'] = args.no_clear
    app['HEADER_NAME'] = args.template_header_name
    app['HEADER_URL'] = args.template_header_url
    # aiohttp_jinja requirement
    app['static_root_url'] = STATIC_URL
    app['debug'] = args.debug
    app['websockets'] = weakref.WeakSet()

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

    return app
