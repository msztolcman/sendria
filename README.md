# MailDump

MailDump is a python-based clone of the awesome [MailCatcher][mailcatcher] tool.
Its purpose is to provide developers a way to let applications send emails without actual emails being sent to anyone.
Additionally lazy developers might prefer this over a real SMTP server simply for the sake of it being much easier and
faster to set up.

## Features

Since the goal of this project is to have the same features as MailCatcher I suggest you to read its readme instead.

## Warning

This is still under heavy development. If you install it don't complain if something doesn't work. Oh, and even when
omitting the `-f` switch the process stays in foreground for now.

## Credits

The layout of the web interface has been taken from MailCatcher. No Copy&Paste involved - I rewrote the SASS/Compass
stylesheet from MailCatcher in SCSS as there is a pure-python implementation of SCSS available.
If whoever reads this feels like creating a new layout that looks as good or even better feel free to send a pull
request. I'd actually prefer a layout that differs from MailCatcher at least a little bit but I'm somewhat bad at
creating layouts!

## License

Copyright © 2013 Adrian Mönnich (adrian@planetcoding.net). Released under the MIT License, see [LICENSE][license] for details.


  [mailcatcher]: https://github.com/sj26/mailcatcher/blob/master/README.md
  [license]: https://github.com/ThiefMaster/maildump/blob/master/LICENSE