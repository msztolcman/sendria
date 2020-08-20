MailTrap
==========

[![mailtrap version](https://img.shields.io/pypi/v/mailtrap.svg)](https://pypi.python.org/pypi/mailtrap)
[![mailtrap license](https://img.shields.io/pypi/l/mailtrap.svg)](https://pypi.python.org/pypi/mailtrap)
[![mailtrap python compatibility](https://img.shields.io/pypi/pyversions/mailtrap.svg)](https://pypi.python.org/pypi/mailtrap)
[![say thanks!](https://img.shields.io/badge/Say%20Thanks-!-1EAEDB.svg)](https://saythanks.io/to/marcin%40urzenia.net)

MailTrap is a SMTP server designed to run in your dev/test environment, that is designed to catch any email you
or your application is sending, and display it in a web interface instead of sending to real world.
It help you prevents sending any dev/test emails to real people, no matter what address you provide.
Just point your app/email client to `smtp://127.0.0.1:1025` and look at your emails on `http://127.0.0.1:1080`.

MailTrap is built on shoulders of:
* [MailCatcher](https://mailcatcher.me/) - original idea comes of this tool by Samuel Cochran.
* [MailDump](https://github.com/ThiefMaster/maildump) - base source code of `MailTrap` (version pre 1.0.0), by Adrian Mönnich.

If you like this tool, just [say thanks](https://saythanks.io/to/marcin%40urzenia.net).

Current stable version
----------------------

1.0.0

Features
--------

* Catch all emails and store it for display.
* Full support for multipart messages.
* View HTML and plain text parts of messages (if given part exists).
* View source of email.
* Lists attachments and allows separate downloading of parts.
* Download original email to view in your native mail client(s).
* Mail appears instantly if your browser supports [WebSockets](https://en.wikipedia.org/wiki/WebSocket).
* Optionally, send webhook on every received message.
* Runs as a daemon in the background, optionally in foreground.
* Keyboard navigation between messages.
* Optionally password protected access to web interface.
* Optionally password protected access to SMTP (SMTP AUTH).
* It's all Python!

Installation
------------

`MailTrap` should work on any POSIX platform where [Python](http://python.org)
is available, it means Linux, MacOS/OSX etc.

Simplest way is to use Python's built-in package system:

    python3 -m pip install mailtrap

You can also use [pipx](https://pipxproject.github.io/pipx/) if you don't want to
mess with system packages and install `MailTrap` in virtual environment:

    pipx install mailtrap

Voila!

Python version
--------------

`MailTrap` is tested against Python 3.7+. Older Python versions may work, or may not.

If you want to run this software on Python 2.6+, just use [MailDump](https://github.com/ThiefMaster/maildump).

How to use
----------

[After installing](#installation) `MailTrap`, just run command:

    mailtrap --db mails.sqlite

Now send emails through `smtp://127.0.0.1:1025`, ie.:

```shell
echo 'From: MailTrap <mailtrap@example.com>\n'\
'To: You <you@exampl.com>\n'\
'Subject: Welcome!\n\n'\
'Welcome to MailTrap!' | \
  curl smtp://localhost:1025 --mail-from mailtrap@example.com \
    --mail-rcpt you@example.com --upload-file -
```

And finally look at `MailTrap` GUI on [127.0.0.1:1080](http://127.0.0.1:1080).

If you want more details, run:

    mailtrap --help

for more info, ie. how to protect access to gui.


API
---

`MailTrap` offers RESTful API you can use to fetch list of messages or particular message, ie. for testing purposes.

You can use excellent [httpie](https://httpie.org/) tool:

```shell
% http localhost:1080/api/messages/
HTTP/1.1 200 OK
Content-Length: 620
Content-Type: application/json; charset=utf-8
Date: Wed, 22 Jul 2020 20:04:46 GMT
Server: MailTrap/1.0.0 (https://github.com/msztolcman/mailtrap)

{
    "code": "OK",
    "data": [
        {
            "created_at": "2020-07-22T20:04:41",
            "id": 1,
            "peer": "127.0.0.1:59872",
            "recipients_envelope": [
                "you@example.com"
            ],
            "recipients_message_bcc": [],
            "recipients_message_cc": [],
            "recipients_message_to": [
                "You <you@exampl.com>"
            ],
            "sender_envelope": "mailtrap@example.com",
            "sender_message": "MailTrap <mailtrap@example.com>",
            "size": 191,
            "source": "From: MailTrap <mailtrap@example.com>\nTo: You <you@exampl.com>\nSubject: Welcome!\nX-Peer: ('127.0.0.1', 59872)\nX-MailFrom: mailtrap@example.com\nX-RcptTo: you@example.com\n\nWelcome to MailTrap!\n",
            "subject": "Welcome!",
            "type": "text/plain"
        }
    ]
}
```

There are available endpoints:

* `GET /api/messages/` - fetch list of all emails
* `DELETE /api/messages/` - delete all emails
* `GET /api/messages/{message_id}.json` - fetch email metadata
* `GET /api/messages/{message_id}.plain` - fetch plain part of email
* `GET /api/messages/{message_id}.html` - fetch HTML part of email
* `GET /api/messages/{message_id}.source` - fetch source of email
* `GET /api/messages/{message_id}.eml` - download whole email as an EML file
* `GET /api/messages/{message_id}/parts/{cid}` - download particular attachment
* `DELETE /api/messages/{message_id}` - delete single email

Docker
------

There is also available [Docker image of MailTrap](https://hub.docker.com/layers/msztolcman/mailtrap/).
If you want to try, just run:

```shell
docker run -p 1025:1025 -p 1080:1080 msztolcman/mailtrap
```

Help!
-----

I'm backend developer, not a frontend guy nor designer... If you are, and want to help, just [mail me!](mailto:marcin@urzenia.net).
I think GUI should be redesigned, or at least few minor issues could be solved. Also, project requires some logo and/or icon. Again,
do not hesitate to [mail me](mailto:marcin@urzenia.net) if you want and can help :)

Configure Rails
---------------

For your rails application just set in your `environments/development.rb`:

    config.action_mailer.delivery_method = :smtp
    config.action_mailer.smtp_settings = { :address => '127.0.0.1', :port => 1025 }
    config.action_mailer.raise_delivery_errors = false

Configure Django
----------------

To configure Django to work with `MailTrap`, add the following to your projects' `settings.py`:

    if DEBUG:
        EMAIL_HOST = '127.0.0.1'
        EMAIL_HOST_USER = ''
        EMAIL_HOST_PASSWORD = ''
        EMAIL_PORT = 1025
        EMAIL_USE_TLS = False

Behind nginx
------------

If you want to hide `MailTrap` behind nginx (ie. to terminate ssl) then you can [use example
config (see in addons)](https://github.com/msztolcman/mailtrap/tree/master/addons/nginx.conf).

Supervisord
-----------

To start `Mailtrap` automatically with [Supervisor](https://supervisord.org/) there is in
[addons example config file for this purpose](https://github.com/msztolcman/mailtrap/tree/master/addons/supervisor.conf).

Authors
-------

* Marcin Sztolcman ([marcin@urzenia.net](mailto:marcin@urzenia.net))
* Adrian Mönnich (author of [MailDump](https://github.com/ThiefMaster/maildump), base of `MailTrap`)

Contact
-------

If you like or dislike this software, please do not hesitate to tell me about
this me via email ([marcin@urzenia.net](mailto:marcin@urzenia.net)).

If you find bug or have an idea to enhance this tool, please use GitHub's
[issues](https://github.com/msztolcman/mailtrap/issues).

ChangeLog
---------

### v1.0.0

* complete rewrite of backend part. MailTrap is using [asyncio](https://docs.python.org/3/library/asyncio.html) and
  [aio-libs](https://github.com/aio-libs/) now:
  * switch to [aiohttp](https://docs.aiohttp.org/) from Flask
  * switch to [aiosmtpd](https://aiosmtpd.readthedocs.io) from [smtpd](https://docs.python.org/3/library/smtpd.html)
  * switch to [aiosqlite](https://github.com/omnilib/aiosqlite) from [sqlite3](https://docs.python.org/3/library/sqlite3.html)
  * changed logger to [structlog](https://www.structlog.org/)
* using asynchronous version of libraries drastically improved performance
* `MailTrap` now can send a webhook about every received message
* show in GUI information about envelope sender and recipients
* all API requests has their own namespace now: `/api`
* allow to replace name of application or url in template
* block truncating all messages from GUI (on demand)
* fixed issues with `WebSockets`, should refresh mails list and reconnect if disconnected
* fixed issues with autobuilding assets
* many cleanups and reformatting code
* addons for [nginx](https://github.com/msztolcman/mailtrap/tree/master/addons/nginx.conf)
and [supervisor](https://github.com/msztolcman/mailtrap/tree/master/addons/supervisor.conf)

#### Backward incompatible changes:

* all api's requests are now prefixed with `/api` (look at [API section](#api))
* `--htpasswd` cli param is renamed to `--http-auth`

### v0.1.6

* fixed issue with old call do `gevent.signal`
* minimum gevent version set to 1.5.0

### v0.1.4

* bumped dependencies - security issues ([dependabot](https://github.com/dependabot))

### v0.1.3

* fixed layout issues ([radoslawhryciow](https://github.com/radoslawhryciow))

### v0.1.2

* fixed encoding issues

### v0.1.0

* better support for macOS/OSX
* links now opens in new tab/window (added 'target="blank"')
* show message if there is no assets generated and info how to to generate them
* added debugs for SMTP when in debug mode
* added support for [Pipenv](https://docs.pipenv.org/)
* HTML tab is default now when looking at particular message
* converted to support Python 3.6+, drop support for lower Python versions
* added SMTP auth support (look at [pull request 28](https://github.com/ThiefMaster/maildump/pull/28) )
* copy from [MailDump](https://github.com/ThiefMaster/maildump) v0.5.6
