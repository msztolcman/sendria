FROM python:3.10-alpine as build
LABEL org.opencontainers.image.authors="Marcin Sztolcman <marcin@urzenia.net>"

ARG VERSION=2.2.2

USER root
RUN addgroup -S sendria && adduser -S sendria -G sendria
RUN apk add --no-cache --upgrade bash
RUN apk --update --no-cache --virtual build-dependencies add apache2-utils
USER sendria
WORKDIR /home/sendria
RUN python3 -m pip install --user sendria==$VERSION
ENV PATH="/home/sendria/.local/bin:$PATH"
ENV SENDRIA_DATA_DIR="/home/sendria/data"
ADD tools /home/sendria/tools

EXPOSE 1025 1080

ENTRYPOINT [ "/home/sendria/tools/docker-entrypoint.sh" ]