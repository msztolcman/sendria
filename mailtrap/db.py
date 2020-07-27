import json
import sqlite3
from typing import Optional

import aiosqlite
import uuid
from contextlib import asynccontextmanager
from email.header import decode_header as _decode_header
from email.utils import getaddresses

from . import logger
from . import webhook
from .http import websocket

_db: Optional[str] = None


async def set_db(db: str):
    global _db
    _db = db

    async with connection() as conn:
        await create_tables(conn)


def decode_header(value):
    if not value:
        return ''
    headers = []
    for decoded, charset in _decode_header(value):
        if isinstance(decoded, str):
            headers.append(decoded.encode(charset or 'utf-8'))
        else:
            headers.append(decoded)
    return (b''.join(headers)).decode()


def split_addresses(value):
    return [('{0} <{1}>'.format(name, addr) if name else addr)
            for name, addr in getaddresses([value])]


def iter_message_parts(message):
    if message.is_multipart():
        for message in message.get_payload():
            for part in iter_message_parts(message):
                yield part
    else:
        yield message


def _parse_recipients(recipients):
    recipients = json.loads(recipients)
    return recipients


@asynccontextmanager
async def connection():
    conn = await aiosqlite.connect(_db, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = aiosqlite.Row
    conn.text_factory = str
    yield conn
    await conn.close()


async def create_tables(conn: aiosqlite.Connection):
    logger.get().msg('DB: creating tables')
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS message (
            id INTEGER PRIMARY KEY ASC,
            sender_envelope TEXT,
            sender_message TEXT,
            recipients_envelope TEXT,
            recipients_message_to TEXT,
            recipients_message_cc TEXT,
            recipients_message_bcc TEXT,
            subject TEXT,
            source BLOB,
            size INTEGER,
            type TEXT,
            peer TEXT,
            created_at TIMESTAMP
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS message_part (
            id INTEGER PRIMARY KEY ASC,
            message_id INTEGER NOT NULL,
            cid TEXT,
            type TEXT,
            is_attachment INTEGER,
            filename TEXT,
            charset TEXT,
            body BLOB,
            size INTEGER,
            created_at TIMESTAMP
        )
    """)


async def add_message(conn: aiosqlite.Connection, sender, recipients_envelope, message, peer):
    sql = """
        INSERT INTO message
            (sender_envelope, sender_message, recipients_envelope, recipients_message_to,
             recipients_message_cc, recipients_message_bcc, subject,
              source, type, size, peer, created_at)
        VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
    """

    body = message.as_string()
    cur = await conn.cursor()
    msg_info = {
        'sender_envelope': decode_header(sender),
        'sender_message': decode_header(message['FROM']),
        'recipients_envelope': recipients_envelope,
        'recipients_message_to': json.dumps(split_addresses(decode_header(message['TO'])) if 'TO' in message else []),
        'recipients_message_cc': json.dumps(split_addresses(decode_header(message['CC'])) if 'CC' in message else []),
        'recipients_message_bcc': json.dumps(split_addresses(decode_header(message['BCC'])) if 'BCC' in message else []),
        'subject': decode_header(message['Subject']),
        'source': body,
        'type': message.get_content_type(),
        'peer': ':'.join([i.strip(" '()")for i in peer.split(',')])
    }
    await cur.execute(
        sql,
        (
            msg_info['sender_envelope'],
            msg_info['sender_message'],
            msg_info['recipients_envelope'],
            msg_info['recipients_message_to'],
            msg_info['recipients_message_cc'],
            msg_info['recipients_message_bcc'],
            msg_info['subject'],
            msg_info['source'],
            msg_info['type'],
            len(body),
            msg_info['peer'],
        )
    )
    message_id = msg_info['message_id'] = cur.lastrowid
    # Store parts (why do we do this for non-multipart at all?!)
    parts = 0
    for part in iter_message_parts(message):
        cid = part.get('Content-Id') or str(uuid.uuid4())
        if cid[0] == '<' and cid[-1] == '>':
            cid = cid[1:-1]
        await _add_message_part(conn, message_id, cid, part)
        parts += 1
    await conn.commit()
    await cur.close()
    logger.get().msg('DB: stored message', message_id=message_id, parts=parts)
    await websocket.broadcast('add_message', message_id)
    await webhook.execute(msg_info)
    return message_id


async def _add_message_part(conn: aiosqlite.Connection, message_id, cid, part):
    sql = """
        INSERT INTO message_part
            (message_id, cid, type, is_attachment, filename, charset, body, size, created_at)
        VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
    """

    body = part.get_payload(decode=True)
    body_len = len(body) if body else 0
    await conn.execute(
        sql,
        (
            message_id,
            cid,
            part.get_content_type(),
            part.get_filename() is not None,
            part.get_filename(),
            part.get_content_charset(),
            body,
            body_len
        )
    )


def _prepare_message_row_inplace(row) -> None:
    row['recipients_envelope'] = split_addresses(row['recipients_envelope'])
    row['recipients_message_to'] = _parse_recipients(row['recipients_message_to'])
    row['recipients_message_cc'] = _parse_recipients(row['recipients_message_cc'])
    row['recipients_message_bcc'] = _parse_recipients(row['recipients_message_bcc'])


async def get_message(conn: aiosqlite.Connection, message_id):
    async with conn.execute('SELECT * FROM message WHERE id = ?', (message_id,)) as cur:
        row = await cur.fetchone()
    if not row:
        return None
    row = dict(row)
    _prepare_message_row_inplace(row)
    return row


async def get_message_attachments(conn: aiosqlite.Connection, message_id):
    sql = """
        SELECT
            message_id, cid, type, filename, size
        FROM
            message_part
        WHERE
            message_id = ? AND
            is_attachment = 1
        ORDER BY
            filename ASC
    """
    async with conn.execute(sql, (message_id,)) as cur:
        data = await cur.fetchall()

    return data


async def _get_message_part_types(conn: aiosqlite.Connection, message_id, types):
    sql = """
        SELECT
            *
        FROM
            message_part
        WHERE
            message_id = ? AND
            type IN ({0}) AND
            is_attachment = 0
        LIMIT
            1
    """.format(','.join('?' * len(types)))

    async with conn.execute(sql, (message_id,) + types) as cur:
        data = await cur.fetchone()
    return data


async def get_message_part_html(conn: aiosqlite.Connection, message_id):
    return await _get_message_part_types(conn, message_id, ('text/html', 'application/xhtml+xml'))


async def get_message_part_plain(conn: aiosqlite.Connection, message_id):
    return await _get_message_part_types(conn, message_id, ('text/plain',))


async def get_message_part_cid(conn: aiosqlite.Connection, message_id, cid):
    async with conn.execute('SELECT * FROM message_part WHERE message_id = ? AND cid = ?', (message_id, cid)) as cur:
        data = await cur.fetchone()
    return data


async def _message_has_types(conn: aiosqlite.Connection, message_id, types):
    sql = """
        SELECT
            1
        FROM
            message_part
        WHERE
            message_id = ? AND
            is_attachment = 0 AND
            type IN ({0})
        LIMIT
            1
    """.format(','.join('?' * len(types)))
    async with conn.execute(sql, (message_id,) + types) as cur:
        data = await cur.fetchone()
    return data is not None


async def message_has_html(conn: aiosqlite.Connection, message_id):
    return await _message_has_types(conn, message_id, ('application/xhtml+xml', 'text/html'))


async def message_has_plain(conn: aiosqlite.Connection, message_id):
    return await _message_has_types(conn, message_id, ('text/plain',))


async def get_messages(conn: aiosqlite.Connection):
    async with conn.execute('SELECT * FROM message ORDER BY created_at ASC') as cur:
        data = await cur.fetchall()

    data = list(map(dict, data))
    for row in data:
        _prepare_message_row_inplace(row)
    return data


async def delete_message(conn: aiosqlite.Connection, message_id):
    await conn.execute('DELETE FROM message WHERE id = ?', (message_id,))
    await conn.execute('DELETE FROM message_part WHERE message_id = ?', (message_id,))
    await conn.commit()
    logger.get().msg('DB: Deleted message {0}'.format(message_id))
    await websocket.broadcast('delete_message', message_id)


async def delete_messages(conn: aiosqlite.Connection):
    await conn.execute('DELETE FROM message')
    await conn.execute('DELETE FROM message_part')
    await conn.commit()
    logger.get().msg('DB: Deleted all messages')
    await websocket.broadcast('delete_messages')
