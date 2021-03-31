FROM python:3.8-slim-buster
LABEL maintainer="Marcin Sztolcman <marcin@urzenia.net>"

RUN python3 -m pip install pipenv
RUN useradd --create-home sendria
USER sendria
COPY --chown=sendria:sendria . /home/sendria/sendria
WORKDIR /home/sendria/sendria
RUN pipenv lock --requirements > requirements.txt
RUN python3 -m pip install --user -r requirements.txt
RUN /home/sendria/.local/bin/webassets -m sendria.build_assets build
RUN python3 setup.py install --user
WORKDIR /home/sendria

EXPOSE 1025 1080

CMD ["/home/sendria/.local/bin/sendria", "--foreground", "--db=./mails.sqlite", "--smtp-ip=0.0.0.0", "--http-ip=0.0.0.0"]
