from logbook import Logger
import json
import sqlite3

log = Logger(__name__)
_conn = None


def connect(db=None):
    global _conn
    db = db or ':memory:'
    log.info('Using database {}'.format(db))
    _conn = sqlite3.connect(db, detect_types=sqlite3.PARSE_DECLTYPES)
    _conn.row_factory = sqlite3.Row


def disconnect():
    global _conn
    if _conn:
        log.debug('Closing database')
        _conn.close()
        _conn = None


def create_tables():
    log.debug('Creating tables')
    _conn.execute("""
        CREATE TABLE IF NOT EXISTS message (
            id INTEGER PRIMARY KEY ASC,
            sender TEXT,
            recipients TEXT,
            subject TEXT,
            source BLOB,
            size INTEGER,
            type TEXT,
            created_at TIMESTAMP
        )
    """)

    _conn.execute("""
        CREATE TABLE IF NOT EXISTS message_part (
            id INTEGER PRIMARY KEY ASC,
            message_id INTEGER NOT NULL,
            cid INTEGER,
            type TEXT,
            is_attachment INTEGER,
            filename TEXT,
            charset TEXT,
            body BLOB,
            size INTEGER,
            created_at TIMESTAMP
        )
    """)


def add_message(sender, recipients, body, message):
    sql = """
        INSERT INTO message
            (sender, recipients, subject, source, type, size, created_at)
        VALUES
            (?, ?, ?, ?, ?, ?, datetime('now'))
    """

    cur = _conn.cursor()
    cur.execute(sql, (sender,
                      json.dumps(recipients),
                      message['Subject'],
                      body,
                      message.get_content_type(),
                      len(body)))
    message_id = cur.lastrowid
    # Store parts (why do we do this for non-multipart at all?!)
    parts = [message] if not message.is_multipart() else message.get_payload()
    for cid, part in enumerate(parts, 1):
        _add_message_part(message_id, cid, part)
    _conn.commit()
    cur.close()
    log.debug('Stored message {} (parts={})'.format(message_id, len(parts)))
    # TODO: Notify websocket clients
    return message_id


def _add_message_part(message_id, cid, part):
    sql = """
        INSERT INTO message_part
            (message_id, cid, type, is_attachment, filename, charset, body, size, created_at)
        VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
    """

    body = part.get_payload()
    _conn.execute(sql, (message_id,
                        cid,
                        part.get_content_type(),
                        part.get_filename() is not None,
                        part.get_filename(),
                        part.get_content_charset(),
                        body,
                        len(body)))


def get_message(message_id):
    row = _conn.execute('SELECT * FROM message WHERE id = ?', (message_id,)).fetchone()
    if not row:
        return None
    row = dict(row)
    row['recipients'] = json.loads(row['recipients'])
    return row


def get_message_attachments(message_id):
    sql = """
        SELECT
            cid, type, filename, size
        FROM
            message_part
        WHERE
            message_id = ? AND
            is_attachment = 1
        ORDER BY
            filename ASC
    """
    return _conn.execute(sql, (message_id,)).fetchall()


def _get_message_part_types(message_id, types):
    sql = """
        SELECT
            *
        FROM
            message_part
        WHERE
            message_id = ? AND
            type IN ({}) AND
            is_attachment = 0
        LIMIT
            1
    """.format(','.join('?' * len(types)))
    return _conn.execute(sql, (message_id,) + types).fetchone()


def get_message_part_html(message_id):
    return _get_message_part_types(message_id, ('text/html', 'application/xhtml+xml'))


def get_message_part_plain(message_id):
    return _get_message_part_types(message_id, ('text/plain',))


def get_message_part_cid(message_id, cid):
    return _conn.execute('SELECT * FROM message_part WHERE id = ? AND cid = ?', (message_id, cid)).fetchone()


def _message_has_types(message_id, types):
    sql = """
        SELECT
            1
        FROM
            message_part
        WHERE
            message_id = ? AND
            is_attachment = 0 AND
            type IN ({})
        LIMIT
            1
    """.format(','.join('?' * len(types)))
    res = _conn.execute(sql, (message_id,) + types).fetchone()
    return res is not None


def message_has_html(message_id):
    return _message_has_types(message_id, ('application/xhtml+xml', 'text/html'))


def message_has_plain(message_id):
    return _message_has_types(message_id, ('text/plain',))


def get_messages(lightweight=False):
    cols = ('sender', 'recipients', 'created_at', 'subject', 'id', 'size') if lightweight else ('*',)
    rows = map(dict, _conn.execute('SELECT {} FROM message'.format(','.join(cols))).fetchall())
    for row in rows:
        row['recipients'] = json.loads(row['recipients'])
    return rows


def delete_message(message_id):
    _conn.execute('DELETE FROM message WHERE id = ?', (message_id,))
    _conn.execute('DELETE FROM message_part WHERE message_id = ?', (message_id,))
    _conn.commit()
    log.debug('Deleted message {}'.format(message_id))
    # TODO: Notify websocket clients


def delete_messages():
    _conn.execute('DELETE FROM message')
    _conn.execute('DELETE FROM message_part')
    _conn.commit()
    log.debug('Deleted all messages')
    # TODO: Notify websocket clients