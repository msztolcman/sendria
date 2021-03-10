__all__ = ['setup', 'connection', 'add_message', 'delete_message', 'delete_messages', 'get_message',
    'get_message_attachments', 'get_message_part_cid', 'get_message_part_html', 'get_message_part_plain',
    'get_messages',
]

import json
import pathlib
import sqlite3
from typing import Iterable, Optional, Union, List

import aiosqlite
import uuid
from contextlib import asynccontextmanager
from email.message import Message
from email.header import decode_header as _decode_header
from email.utils import getaddresses

from . import logger
from . import callback
from . import notifier

_db: Optional[str] = None


async def setup(db: Union[str, pathlib.Path]) -> None:
    global _db
    _db = str(db)

    async with connection() as conn:
        await create_tables(conn)
        logger.get().msg('DB initialized')


def decode_header(value: Union[str, bytes, None]) -> str:
    if not value:
        return ''
    headers = []
    for decoded, charset in _decode_header(value):
        if isinstance(decoded, str):
            headers.append(decoded.encode(charset or 'utf-8'))
        else:
            headers.append(decoded)
    return (b''.join(headers)).decode()


def split_addresses(value) -> List[str]:
    return [('{0} <{1}>'.format(name, addr) if name else addr)
            for name, addr in getaddresses([value])]


def iter_message_parts(message: Message):
    if message.is_multipart():
        for message in message.get_payload():
            for part in iter_message_parts(message):
                yield part
    else:
        yield message


def _parse_recipients(recipients: Optional[str]) -> List[str]:
    if not recipients:
        return []
    recipients = json.loads(recipients)
    return recipients


@asynccontextmanager
async def connection():
    conn = await aiosqlite.connect(_db, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = aiosqlite.Row
    conn.text_factory = str
    try:
        yield conn
    finally:
        await conn.close()


async def create_tables(conn: aiosqlite.Connection) -> None:
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


async def add_message(conn: aiosqlite.Connection, sender, recipients_envelope, message, peer) -> int:
    sql = """
        INSERT INTO message
            (sender_envelope, sender_message, recipients_envelope, recipients_message_to,
             recipients_message_cc, recipients_message_bcc, subject,
              source, type, size, peer, created_at)
        VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
    """

    body = message.as_string()
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

    parts = []
    for part in iter_message_parts(message):
        cid = part.get('Content-Id') or str(uuid.uuid4())
        if cid[0] == '<' and cid[-1] == '>':
            cid = cid[1:-1]
        parts.append({'cid': cid, 'part': part})

    cur = await conn.cursor()
    await cur.execute('BEGIN')

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
    for part in parts:
        await _add_message_part(cur, message_id, part['cid'], part['part'])
    await cur.execute('COMMIT')
    await cur.close()

    logger.get().msg('message stored', message_id=message_id, parts=parts)
    await notifier.broadcast('add_message', message_id)
    await callback.enqueue(msg_info)
    return message_id


async def _add_message_part(cur: aiosqlite.Cursor, message_id: int, cid: str, part) -> None:
    sql = """
        INSERT INTO message_part
            (message_id, cid, type, is_attachment, filename, charset, body, size, created_at)
        VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
    """

    body = part.get_payload(decode=True)
    body_len = len(body) if body else 0
    await cur.execute(
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


def _prepare_message_row_inplace(row: dict) -> None:
    row['recipients_envelope'] = split_addresses(row['recipients_envelope'])
    row['recipients_message_to'] = _parse_recipients(row['recipients_message_to'])
    row['recipients_message_cc'] = _parse_recipients(row['recipients_message_cc'])
    row['recipients_message_bcc'] = _parse_recipients(row['recipients_message_bcc'])


async def get_message(conn: aiosqlite.Connection, message_id: int) -> Optional[dict]:
    async with conn.execute('SELECT * FROM message WHERE id = ?', (message_id,)) as cur:
        row = await cur.fetchone()
    if not row:
        return None
    row = dict(row)
    _prepare_message_row_inplace(row)
    return row


async def get_message_attachments(conn: aiosqlite.Connection, message_id: int) -> Iterable[sqlite3.Row]:
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


async def _get_message_part_types(conn: aiosqlite.Connection, message_id: int, types: List[str]) -> sqlite3.Row:
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


async def get_message_part_html(conn: aiosqlite.Connection, message_id: int) -> sqlite3.Row:
    return await _get_message_part_types(conn, message_id, ('text/html', 'application/xhtml+xml'))


async def get_message_part_plain(conn: aiosqlite.Connection, message_id: int) -> sqlite3.Row:
    return await _get_message_part_types(conn, message_id, ('text/plain',))


async def get_message_part_cid(conn: aiosqlite.Connection, message_id: int, cid: str) -> sqlite3.Row:
    async with conn.execute('SELECT * FROM message_part WHERE message_id = ? AND cid = ?', (message_id, cid)) as cur:
        data = await cur.fetchone()
    return data


async def _message_has_types(conn: aiosqlite.Connection, message_id: int, types: List[str]) -> bool:
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


async def message_has_html(conn: aiosqlite.Connection, message_id: int) -> bool:
    return await _message_has_types(conn, message_id, ('application/xhtml+xml', 'text/html'))


async def message_has_plain(conn: aiosqlite.Connection, message_id: int) -> bool:
    return await _message_has_types(conn, message_id, ('text/plain',))


async def get_messages(conn: aiosqlite.Connection) -> List[dict]:
    async with conn.execute('SELECT * FROM message ORDER BY created_at ASC') as cur:
        data = await cur.fetchall()

    data = list(map(dict, data))
    for row in data:
        _prepare_message_row_inplace(row)
    return data


async def delete_message(conn: aiosqlite.Connection, message_id: int) -> None:
    await conn.execute('DELETE FROM message WHERE id = ?', (message_id,))
    await conn.execute('DELETE FROM message_part WHERE message_id = ?', (message_id,))
    await conn.commit()
    logger.get().msg('message deleted', message_id=message_id)
    await notifier.broadcast('delete_message', message_id)


async def delete_messages(conn: aiosqlite.Connection) -> None:
    await conn.execute('DELETE FROM message')
    await conn.execute('DELETE FROM message_part')
    await conn.commit()
    logger.get().msg('all messages deleted')
    await notifier.broadcast('delete_messages')
