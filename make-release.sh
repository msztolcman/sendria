#!/bin/bash

# Delete existing (old) assets
rm -rf mailtrap/static/.webassets-cache/ mailtrap/static/assets/bundle.*
# Build current assets
webassets -m mailtrap.web build
webassets -m mailtrap.web build --production
# Create and update release
python setup.py sdist upload
# Delete assets again, we don't need them anymore
rm -rf mailtrap/static/.webassets-cache/ mailtrap/static/assets/bundle.*
