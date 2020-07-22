__all__ = ['get_server']

import binascii
import email.message
from typing import Union

import aiosmtpd.controller
import aiosmtpd.handlers
import aiosmtpd.smtp
from passlib.apache import HtpasswdFile

from . import db
from . import logger


class AsyncMessage(aiosmtpd.handlers.AsyncMessage):
    def __init__(self, *args, smtp_auth=None, **kwargs):
        self._smtp_auth = smtp_auth

        super().__init__(*args, **kwargs)

    async def handle_EHLO(self, server, session, envelope, hostname):
        session.host_name = hostname

        ret = ''
        if self._smtp_auth:
            ret += '250-AUTH PLAIN\n'

        ret += '250 HELP'
        return ret

    async def handle_message(self, message: email.message.Message):
        body = message.get_payload()
        logger.get().msg("message received",
            envelope_from=message['X-MailFrom'],
            envelope_to=message['X-RcptTo'],
            peer=message['X-Peer'],
            length=len(body)
        )
        async with db.connection() as conn:
            await db.add_message(conn, message['X-MailFrom'], message['X-RcptTo'], message, message['X-Peer'])


class SMTP(aiosmtpd.smtp.SMTP):
    def __init__(self, handler, smtp_auth, debug, *args, **kwargs):
        self._authorized = False
        self._smtp_auth = smtp_auth
        self._debug_mode = debug
        self._username = None

        super().__init__(handler, *args, **kwargs)

    def _debug(self, message, **params):
        if self._debug_mode:
            logger.get().msg('SMTP: ' + message, **params)

    def is_valid_user(self, auth_data):
        auth_data_parts = auth_data.split('\x00')
        if len(auth_data_parts) != 3:
            return False

        self._username = auth_data_parts[1]

        if not auth_data.startswith('\x00') and auth_data_parts[0] != auth_data_parts[1]:
            return False

        return self._smtp_auth.check_password(auth_data_parts[1], auth_data_parts[2])

    @aiosmtpd.smtp.syntax('AUTH PLAIN auth-string')
    async def smtp_AUTH(self, arg):
        # print(arg)
        if not self.session.host_name:
            await self.push('503 Error: send EHLO/HELO first')
            return

        if not self._smtp_auth:
            self._debug('AUTH received but authorization is disabled')
            await self.push('501 Syntax: AUTH not enabled')
            return

        if not arg:
            self._debug('AUTH: missing param')
            await self.push('501 Syntax: AUTH TYPE base64(username\\x00username\\x00password)')
            return

        if not arg.lower().startswith('plain '):
            self._debug('AUTH: unknown AUTH method', param=arg)
            await self.push('501 Syntax: only PLAIN auth possible')
            return

        auth_type, auth_data = arg.split(None, 1)
        try:
            auth_data = binascii.a2b_base64(auth_data.strip()).decode()
        except binascii.Error:
            self._debug('AUTH: bad formatted param', param=arg)
            await self.push('535 5.7.8 Authentication credentials invalid')
            return

        if self.is_valid_user(auth_data):
            self._debug('AUTH: credentials accepted', user=self._username)
            await self.push('235 Authentication successful')
            self._authorized = True
            return

        self._debug('AUTH: invalid credentials', user=self._username)
        self._authorized = False
        await self.push('535 5.7.8 Authentication credentials invalid')

    async def smtp_VRFY(self, arg):
        if self._smtp_auth and not self._authorized:
            self._debug('VRFY: not authorized')
            await self.push('530 5.7.0  Authentication required')
            return
        return await super().smtp_VRFY(arg)

    async def smtp_MAIL(self, arg):
        if self._smtp_auth and not self._authorized:
            self._debug('MAIL: not authorized')
            await self.push('530 5.7.0  Authentication required')
            return
        return await super().smtp_MAIL(arg)

    async def smtp_RCPT(self, arg):
        if self._smtp_auth and not self._authorized:
            self._debug('RCPT: not authorized')
            await self.push('530 5.7.0  Authentication required')
            return
        return await super().smtp_RCPT(arg)

    async def smtp_DATA(self, arg):
        if self._smtp_auth and not self._authorized:
            self._debug('DATA: not authorized')
            await self.push('530 5.7.0  Authentication required')
            return
        return await super().smtp_DATA(arg)


class Controller(aiosmtpd.controller.Controller):
    def __init__(self, handler, smtp_auth, debug, *args, **kwargs):
        self.smtp_auth = smtp_auth
        self.debug = debug

        super().__init__(handler, *args, **kwargs)

    def factory(self):
        return SMTP(self.handler, self.smtp_auth, self.debug)


def get_server(smtp_host: str, smtp_port: int, smtp_auth: Union[HtpasswdFile, None], debug: bool):
    message = AsyncMessage(smtp_auth=smtp_auth)
    controller = Controller(message, smtp_auth, debug, hostname=smtp_host, port=smtp_port)

    return controller
