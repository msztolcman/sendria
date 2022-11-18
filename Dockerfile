FROM python:3.10-alpine as build
LABEL org.opencontainers.image.authors="Marcin Sztolcman <marcin@urzenia.net>"

ARG VERSION=2.2.2

RUN addgroup -S sendria && adduser -S sendria -G sendria
WORKDIR /home/sendria
USER sendria
RUN python3 -m pip install --user sendria==$VERSION
RUN chmod 0755 .local
ENV PATH="/home/sendria/.local/bin:$PATH"

EXPOSE 1025 1080

ENTRYPOINT [ "sendria", "--foreground", "--db=./mails.sqlite", "--smtp-ip=0.0.0.0", "--http-ip=0.0.0.0" ]
