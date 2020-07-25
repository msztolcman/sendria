FROM python:3.7
MAINTAINER Marcin Sztolcman <marcin@urzenia.net>

WORKDIR /opt

RUN python3 -m pip install mailtrap==0.1.6

EXPOSE 1025 1080

ENTRYPOINT ["mailtrap", "--foreground", "--db=./mails.sqlite", "--smtp-ip=0.0.0.0", "--http-ip=0.0.0.0"]
