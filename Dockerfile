FROM python:3.8-slim-bullseye

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential \
      gcc \
      git \
      libffi-dev \
      libjpeg62-turbo-dev \
      libldap2-dev \
      libpq-dev \
      libsasl2-dev \
      libssl-dev \
      libxml2-dev \
      libxslt1-dev \
      zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /plone/instance

COPY requirements.txt /plone/instance/requirements.txt
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY buildout.cfg /plone/instance/buildout.cfg
COPY src /plone/instance/src
RUN buildout -c buildout.cfg

# Migration runners change frequently. Copy them only after the expensive
# Plone/buildout layer so editing a tool does not reinstall all dependencies.
COPY tools /plone/instance/tools

RUN mkdir -p /plone/instance/var/filestorage /plone/instance/var/blobstorage \
    && chown -R 1000:1000 /plone/instance

USER 1000:1000
EXPOSE 8070

CMD ["bin/instance", "fg"]
