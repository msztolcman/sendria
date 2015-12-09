MailDump
========

MailDump is a python-based clone of the awesome `MailCatcher`_ tool. Its
purpose is to provide developers a way to let applications send emails
without actual emails being sent to anyone. Additionally lazy developers
might prefer this over a real SMTP server simply for the sake of it
being much easier and faster to set up.

Features
--------

Since the goal of this project is to have the same features as
MailCatcher I suggest you to read its readme instead.

However, there is one unique feature in MailDump: Password protection for
the web interface. If your MailDump instance is listening on a public IP
you might not want your whole company to have access to it. Instead you can
use an Apache-style htpasswd file. I have tested it with SHA-encrypted
passwords but you can use any encryption supported by `passlib.apache`_.

Usage
-----

After installing maildump, run ``maildump --help`` for a list of available
command line arguments.  By default maildump runs its webserver on port
1080 and its SMTP server on port 1025 (both only available via localhost).
Unless you specify a database file, received mails are lost when maildump
terminates.

Credits
-------

The layout of the web interface has been taken from MailCatcher. No
Copy&Paste involved - I rewrote the SASS/Compass stylesheet from
MailCatcher in SCSS as there is a pure-python implementation of SCSS
available. If whoever reads this feels like creating a new layout that
looks as good or even better feel free to send a pull request. I'd
actually prefer a layout that differs from MailCatcher at least a little
bit but I'm somewhat bad at creating layouts!

The icon was created by `Tobia Crivellari`_.

License
-------

Copyright © 2013-2015 Adrian Mönnich (adrian@planetcoding.net). Released
under the MIT License, see `LICENSE`_ for details.

.. _MailCatcher: https://github.com/sj26/mailcatcher/blob/master/README.md
.. _passlib.apache: http://pythonhosted.org/passlib/lib/passlib.apache.html
.. _Tobia Crivellari: http://dribbble.com/TobiaCrivellari
.. _LICENSE: https://github.com/ThiefMaster/maildump/blob/master/LICENSE
