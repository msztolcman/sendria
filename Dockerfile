FROM python:3.8-slim-buster
MAINTAINER Marcin Sztolcman <marcin@urzenia.net>

RUN useradd --create-home mailtrap
WORKDIR /home/mailtrap
USER mailtrap
RUN python3 -m pip install --user mailtrap==1.0.0

EXPOSE 1025 1080

CMD ["/home/mailtrap/.local/bin/mailtrap", "--foreground", "--db=./mails.sqlite", "--smtp-ip=0.0.0.0", "--http-ip=0.0.0.0"]

