#!/usr/bin/env python3
# This is a small utility to run mailtrap during development without installing it first.

import asyncio


if __name__ == '__main__':
    import mailtrap.cli
    # asyncio.run(mailtrap.cli.main())
    mailtrap.cli.main()
