import binascii
import smtpd
from email.parser import Parser

from logbook import Logger
from passlib.apache import HtpasswdFile

from maildump.db import add_message


log = Logger(__name__)


class SMTPChannel(smtpd.SMTPChannel):
    def __init__(self, server, conn, addr, data_size_limit=smtpd.DATA_SIZE_DEFAULT,
                 map=None, enable_SMTPUTF8=False, decode_data=False):
        super().__init__(server, conn, addr, data_size_limit, map, enable_SMTPUTF8, decode_data)

        self._smtp_auth = server.smtp_auth
        self._authorized = False
        self._username = None

    def _debug(self, message, *params):
        log.debug(message, *params)

    def is_valid_user(self, auth_data):
        auth_data_splitted = auth_data.split('\x00')
        if len(auth_data_splitted) != 3:
            return False

        self._username = auth_data_splitted[1]

        if not auth_data.startswith('\x00') and auth_data_splitted[0] != auth_data_splitted[1]:
            return False

        return self._smtp_auth.check_password(auth_data_splitted[1], auth_data_splitted[2])

    def smtp_EHLO(self, arg):
        if not arg:
            self._debug('EHLO: Invalid EHLO: missing param')
            self.push('501 Syntax: EHLO hostname')
            return
        # See issue #21783 for a discussion of this behavior.
        if self.seen_greeting:
            self._debug('EHLO: Duplicate EHLO')
            self.push('503 Duplicate HELO/EHLO')
            return
        self._set_rset_state()
        self.seen_greeting = arg
        self.extended_smtp = True
        self.push('250-%s' % self.fqdn)
        if self.data_size_limit:
            self.push('250-SIZE %s' % self.data_size_limit)
            self.command_size_limits['MAIL'] += 26
        if not self._decode_data:
            self.push('250-8BITMIME')
        if self.enable_SMTPUTF8:
            self.push('250-SMTPUTF8')
            self.command_size_limits['MAIL'] += 10
        if self._smtp_auth:
            self.push('250-AUTH PLAIN')
        self.push('250 HELP')
        self._debug('EHLO: accepted: {}', arg)

    def smtp_AUTH(self, arg):
        if not self.seen_greeting:
            self._debug('AUTH: before EHLO/HELO')
            self.push('503 Error: send EHLO/HELO first')
            return
        if not self._smtp_auth:
            self._debug('AUTH: AUTH received but authorization is disabled')
            self.push('501 Syntax: AUTH not enabled')
            return

        if not arg:
            self._debug('AUTH: missing param')
            self.push('501 Syntax: AUTH TYPE base64(username\\x00username\\x00password)')
            return

        if not arg.lower().startswith('plain '):
            self._debug('AUTH: unknown AUTH method: {}', arg)
            self.push('501 Syntax: only PLAIN auth possible')
            return

        auth_type, auth_data = arg.split(None, 1)
        try:
            auth_data = binascii.a2b_base64(auth_data.strip()).decode()
        except binascii.Error:
            self._debug('AUTH: bad formatted param: {}', arg)
            self.push('535 5.7.8 Authentication credentials invalid')
            return

        if self.is_valid_user(auth_data):
            self._debug('AUTH: credentials accepted for user {}', self._username)
            self.push('235 Authentication successful')
            self._authorized = True
            return

        self._debug('AUTH: invalid credentials for user {}', self._username)
        self._authorized = False
        self.push('535 5.7.8 Authentication credentials invalid')

    def smtp_VRFY(self, arg):
        if self._smtp_auth and not self._authorized:
            self._debug('VRFY: not authorized')
            self.push('530 5.7.0  Authentication required')
            return
        super().smtp_VRFY(arg)

    def smtp_MAIL(self, arg):
        if self._smtp_auth and not self._authorized:
            self._debug('MAIL: not authorized')
            self.push('530 5.7.0  Authentication required')
            return
        super().smtp_MAIL(arg)

    def smtp_RCPT(self, arg):
        if self._smtp_auth and not self._authorized:
            self._debug('RCPT: not authorized')
            self.push('530 5.7.0  Authentication required')
            return
        super().smtp_RCPT(arg)

    def smtp_DATA(self, arg):
        if self._smtp_auth and not self._authorized:
            self._debug('DATA: not authorized')
            self.push('530 5.7.0  Authentication required')
            return
        super().smtp_DATA(arg)


class SMTPServer(smtpd.SMTPServer):
    channel_class = SMTPChannel

    def __init__(self, listener, handler, smtp_auth, debug):
        super(SMTPServer, self).__init__(listener, None)
        self._handler = handler
        self.smtp_auth = smtp_auth
        self.debug = debug

    def process_message(self, peer, mailfrom, rcpttos, data, **kwargs):
        return self._handler(sender=mailfrom, recipients=rcpttos, body=data)


def smtp_handler(sender, recipients, body):
    body = body.decode()
    message = Parser().parsestr(body)
    log.info("Received message from '{0}' ({1} bytes)".format(message['from'] or sender, len(body)))
    add_message(sender, recipients, body, message)
