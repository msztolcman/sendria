#!/bin/bash

# Delete existing (old) assets
rm -rf maildump/static/.webassets-cache/ maildump/static/assets/bundle.*
# Build current assets
webassets -m maildump.web build
webassets -m maildump.web build --production
# Create and update release
python setup.py sdist upload
# Delete assets again, we don't need them anymore
rm -rf maildump/static/.webassets-cache/ maildump/static/assets/bundle.*
