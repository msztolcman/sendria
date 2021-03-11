__all__ = []

from email.message import Message as EmailMessage
from typing import Optional

import aiosmtpd.controller
import aiosmtpd.handlers
import aiosmtpd.smtp
from passlib.apache import HtpasswdFile
from structlog import get_logger

from . import db
from .message import Message

logger = get_logger()


class AsyncMessage(aiosmtpd.handlers.AsyncMessage):
    def __init__(self, *args, smtp_auth=None, **kwargs):
        self._smtp_auth = smtp_auth

        super().__init__(*args, **kwargs)

    async def handle_message(self, email: EmailMessage):
        logger.debug("message received",
            envelope_from=email['X-MailFrom'],
            envelope_to=email['X-RcptTo'],
            peer=':'.join([i.strip(" '()")for i in email['X-Peer'].split(',')]),
        )
        db.add_message(Message.from_email(email))


class SMTP(aiosmtpd.smtp.SMTP):
    def __init__(self, handler, smtp_auth, *args, **kwargs):
        self._smtp_auth = smtp_auth
        self._username = None

        super().__init__(
            handler,
            auth_required=smtp_auth is not None,
            auth_require_tls=False,
            auth_callback=self.authenticate,
            *args, **kwargs
        )

    def authenticate(self, mechanism, login, password):
        return self._smtp_auth.check_password(login, password)


class Controller(aiosmtpd.controller.Controller):
    def __init__(self, handler, smtp_auth, debug, *args, **kwargs):
        self.smtp_auth = smtp_auth
        self.debug = debug
        self.ident = kwargs.pop('ident')

        # TODO: extract connect and total to some kind of settings/cli params
        super().__init__(handler, ready_timeout=5.0, *args, **kwargs)

    def factory(self):
        return SMTP(self.handler, self.smtp_auth, ident=self.ident, hostname=self.hostname)


def run(smtp_host: str, smtp_port: int, smtp_auth: Optional[HtpasswdFile], ident: Optional[str], debug: bool):
    message = AsyncMessage(smtp_auth=smtp_auth)
    controller = Controller(message, smtp_auth, debug, hostname=smtp_host, port=smtp_port, ident=ident)
    controller.start()

    return controller
