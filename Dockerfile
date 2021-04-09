ARG SENDRIA_BUILD_VERSION=prod
ARG SENDRIA_VERSION_FOR_DOCKER=2.2.2
#LABEL maintainer="Marcin Sztolcman <marcin@urzenia.net>"

FROM python:3.8-slim-buster AS base
RUN useradd --create-home sendria
WORKDIR /home/sendria
USER sendria

EXPOSE 1025 1080

FROM base AS install-dev
COPY --from=base /home/sendria /home/sendria
COPY --from=base /etc /etc
COPY --chown=sendria:sendria . /home/sendria
RUN python3 -m pip install pipenv && python3 -m pipenv install --dev && python3 -m pipenv run webassets -m sendria.build_assets build
CMD ["python3", "-m", "pipenv", "run", "sendria", "--foreground", "--db=./mails.sqlite", "--smtp-ip=0.0.0.0", "--http-ip=0.0.0.0"]

FROM base AS install-prod
COPY --from=base /home/sendria /home/sendria
COPY --from=base /etc /etc
RUN python3 -m pip install --user sendria==2.2.2
CMD ["/home/sendria/.local/bin/sendria", "--foreground", "--db=./mails.sqlite", "--smtp-ip=0.0.0.0", "--http-ip=0.0.0.0"]

FROM install-${SENDRIA_BUILD_VERSION} AS install-final

FROM install-final
