__all__ = ['Message']

import uuid
from email.header import decode_header as _decode_header
from email.message import Message as EmailMessage
from email.utils import getaddresses
from typing import Union, List, Dict, Any


class Message:
    __slots__ = (
        'id',
        'sender_envelope', 'sender_message',
        'recipients_envelope', 'recipients_message_to',
        'recipients_message_cc', 'recipients_message_bcc',
        'subject',
        'source',
        'size', 'type', 'peer',
        'parts',
        'created_at',
    )

    @classmethod
    def from_email(cls, email: EmailMessage) -> 'Message':
        o = cls()
        o.id = None
        o.sender_envelope = cls.decode_header(email['X-MailFrom'])
        o.sender_message = cls.decode_header(email['FROM'])
        o.recipients_envelope = email['X-RcptTo']
        o.recipients_message_to = cls.split_addresses(cls.decode_header(email['TO'])) if 'TO' in email else []
        o.recipients_message_cc = cls.split_addresses(cls.decode_header(email['CC'])) if 'CC' in email else []
        o.recipients_message_bcc = cls.split_addresses(cls.decode_header(email['BCC'])) if 'BCC' in email else []
        o.subject = cls.decode_header(email['Subject'])
        o.source = email.as_string()
        o.size = len(o.source)
        o.type = email.get_content_type()
        o.peer = ':'.join([i.strip(" '()")for i in email['X-Peer'].split(',')])
        o.parts = []
        o.created_at = None

        for part in cls.iter_message_parts(email):
            cid = part.get('Content-Id') or str(uuid.uuid4())
            if cid[0] == '<' and cid[-1] == '>':
                cid = cid[1:-1]
            o.parts.append({'cid': cid, 'part': part})

        return o

    def to_dict(self) -> Dict[str, Any]:
        return {
            k: getattr(self, k)
            for k in self.__slots__
        }

    def __repr__(self) -> str:
        r = []
        for k in self.__slots__:
            if k not in ('source', 'parts'):
                r.append(f'{k}={getattr(self, k)}')
            else:
                r.append(f'{k}=...')
        return f'<EmailMessage: {", ".join(r)}>'

    @classmethod
    def decode_header(cls, value: Union[str, bytes, None]) -> str:
        if not value:
            return ''
        headers = []
        for decoded, charset in _decode_header(value):
            if isinstance(decoded, str):
                headers.append(decoded.encode(charset or 'utf-8'))
            else:
                headers.append(decoded)
        return (b''.join(headers)).decode()

    @classmethod
    def split_addresses(cls, value: str) -> List[str]:
        return [('{0} <{1}>'.format(name, addr) if name else addr)
            for name, addr in getaddresses([value])]

    @classmethod
    def iter_message_parts(cls, email: EmailMessage) -> EmailMessage:
        if email.is_multipart():
            for payload in email.get_payload():
                for part in cls.iter_message_parts(payload):
                    yield part
        else:
            yield email
