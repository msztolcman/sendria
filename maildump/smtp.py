import base64
import smtpd
from email.parser import Parser

from logbook import Logger
from passlib.apache import HtpasswdFile

from maildump.db import add_message


log = Logger(__name__)


class SMTPChannel(smtpd.SMTPChannel, object):
    def __init__(self, server, conn, addr, smtp_auth):
        super(SMTPChannel, self).__init__(server, conn, addr)
        self._smtp_auth = smtp_auth
        self._authorized = False

    def smtp_EHLO(self, arg):
        if not arg:
            self.push('501 Syntax: EHLO hostname')
            return
        if self.__greeting:
            self.push('503 Duplicate HELO/EHLO')
            return
        self.__greeting = arg
        self.push('250-%s' % self.__fqdn)
        if self._smtp_auth:
            self.push('250-AUTH PLAIN')
        self.push('250 HELP')

    def smtp_AUTH(self, arg):
        print >> smtpd.DEBUGSTREAM, '===> AUTH', arg
        if not self._smtp_auth:
            self.push('501 Syntax: AUTH not enabled')
            return

        if not arg:
            self.push('501 Syntax: AUTH TYPE base64(username:password)')
            return

        if not arg.lower().startswith('plain '):
            self.push('501 Syntax: only PLAIN auth possible')
            return

        auth_type, auth_data = arg.split(None, 1)
        try:
            auth_data = base64.b64decode(auth_data.strip())
        except TypeError:
            self.push('535 5.7.8 Authentication credentials invalid')
            return

        auth_data = auth_data.split('\x00')
        if (len(auth_data) == 3 and auth_data[0] == auth_data[1] and
                self._smtp_auth.check_password(auth_data[1], auth_data[2])):
            self.push('235 Authentication successful')
            self._authorized = True
            return

        self._authorized = False
        self.push('535 5.7.8 Authentication credentials invalid')

    def smtp_MAIL(self, arg):
        if self._smtp_auth and not self._authorized:
            self.push('530 5.7.0  Authentication required')
            return
        super(SMTPChannel, self).smtp_MAIL(arg)

    def smtp_RCPT(self, arg):
        if self._smtp_auth and not self._authorized:
            self.push('530 5.7.0  Authentication required')
            return
        super(SMTPChannel, self).smtp_RCPT(arg)

    def smtp_DATA(self, arg):
        if self._smtp_auth and not self._authorized:
            self.push('530 5.7.0  Authentication required')
            return
        super(SMTPChannel, self).smtp_DATA(arg)


class SMTPServer(smtpd.SMTPServer, object):
    def __init__(self, listener, handler, smtp_auth):
        super(SMTPServer, self).__init__(listener, None)
        self._handler = handler
        self._smtp_auth = smtp_auth

    def handle_accept(self):
        pair = self.accept()
        if pair is not None:
            conn, addr = pair
            print >> smtpd.DEBUGSTREAM, 'Incoming connection from %s' % repr(addr)
            channel = SMTPChannel(self, conn, addr, self._smtp_auth)

    def process_message(self, peer, mailfrom, rcpttos, data):
        return self._handler(sender=mailfrom, recipients=rcpttos, body=data)


def smtp_handler(sender, recipients, body):
    message = Parser().parsestr(body)
    log.info("Received message from '{0}' ({1} bytes)".format(message['from'] or sender, len(body)))
    add_message(sender, recipients, body, message)
