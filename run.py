#!/usr/bin/env python3
# This is a small utility to run sendria during development without installing it first.

import asyncio


if __name__ == '__main__':
    import sendria.cli
    # asyncio.run(sendria.cli.main())
    sendria.cli.main()
