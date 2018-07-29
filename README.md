MailTrap
==========

[![mailtrap version](https://img.shields.io/pypi/v/mailtrap.svg)](https://pypi.python.org/pypi/mailtrap)
[![mailtrap license](https://img.shields.io/pypi/l/mailtrap.svg)](https://pypi.python.org/pypi/mailtrap)
[![mailtrap python compatibility](https://img.shields.io/pypi/pyversions/mailtrap.svg)](https://pypi.python.org/pypi/mailtrap)
[![say thanks!](https://img.shields.io/badge/Say%20Thanks-!-1EAEDB.svg)](https://saythanks.io/to/msztolcman)

MailTrap is a SMTP server designed to run in your dev/test environment, that is designed to catch any email you or your application is sending, and display it in a web interface instead if sending to real world. It help you prevents sending any dev/test emails to real people, no matter what address you provide.
Just point your app/email client to smtp://127.0.0.1:1025 and look at your emails on http://127.0.0.1/1080.

MailTrap is built on shoulders of:
* [MailCatcher](https://mailcatcher.me/) - original idea comes of this tool by Samuel Cochran.
* [MailDump](https://github.com/ThiefMaster/maildump) - base source code of `MailTrap`, by Adrian Mönnich.

If you like this tool, just [say thanks](https://saythanks.io/to/msztolcman).

Current stable version
----------------------

0.1.1

Features
--------

* Catches all mail and stores it for display.
* Shows HTML, Plain Text and Source version of messages, as applicable.
* Rewrites HTML enabling display of embedded, inline images/etc and opens links in a new window.
* Lists attachments and allows separate downloading of parts.
* Download original email to view in your native mail client(s).
* Command line options to override the default SMTP/HTTP IP and port settings.
* Mail appears instantly if your browser supports [WebSockets][websockets], otherwise updates every thirty seconds.
* Runs as a daemon in the background, optionally in foreground.
* Keyboard navigation between messages
* Optionally password protected access to webinterface
* Optionally password protected access to SMTP (SMTP AUTH)

How to use
----------

After installing `MailTrap`, just run command:

    mailtrap

Now send emails through `smtp://127.0.0.1:1025` and look at them on `http://127.0.0.1:1080`.

If you want more details, run:

    mailtrap --help
    
for more info, ie. how to protect access to gui.

Python version
--------------

`MailTrap` is tested against Python 3.6+. Older Python versions may work, or may not.

Installation
------------

`MailTrap` should work on any POSIX platform where [Python](http://python.org)
is available, it means Linux, MacOS X etc. 

Simplest way is to use Python's built-in package system:

    pip3 install mailtrap

Voila!

Authors
-------

* Marcin Sztolcman <marcin@urzenia.net>
* Adrian Mönnich ([MailDump](https://github.com/ThiefMaster/maildump))

Contact
-------

If you like or dislike this software, please do not hesitate to tell me about
this me via email (marcin@urzenia.net).

If you find bug or have an idea to enhance this tool, please use GitHub's
[issues](https://github.com/msztolcman/mailtrap/issues).

License
-------

The MIT License (MIT)

Copyright (c) 2018 Marcin Sztolcman
Copyright (c) 2013 Adrian Mönnich ([MailDump](https://github.com/ThiefMaster/maildump))

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in
the Software without restriction, including without limitation the rights to
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
the Software, and to permit persons to whom the Software is furnished to do so,
subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

ChangeLog
---------

### v0.1.0

* better support for macOS/OSX
* links now opens in new tab/window (added 'target="blank"')
* show message if there is no assets generated and info hoto to generate them
* added debugs for SMTP when in debug mode
* added support for [Pipenv](https://docs.pipenv.org/)
* HTML tab is default now when looking at particular message
* converted to support Python 3.6+, drop support for lower Python versions
* added SMTP auth support (look at [pull request 28](https://github.com/ThiefMaster/maildump/pull/28) )
* copy from [MailDump](https://github.com/ThiefMaster/maildump) v0.5.6
