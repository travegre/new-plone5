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

# Buildout needs the develop package to exist, but it does not need the full
# application source merely to resolve/install Plone and third-party eggs.
# Keep this skeleton stable so normal Python/ZCML/template/resource edits do
# not invalidate the expensive Buildout dependency layer.
RUN mkdir -p /plone/instance/src/imi.migration/src/imi/migration
COPY src/imi.migration/setup.py /plone/instance/src/imi.migration/setup.py
COPY src/imi.migration/src/imi/__init__.py /plone/instance/src/imi.migration/src/imi/__init__.py
COPY src/imi.migration/src/imi/migration/__init__.py /plone/instance/src/imi.migration/src/imi/migration/__init__.py
RUN buildout -c buildout.cfg

# Application source changes frequently. The develop egg created above points
# at this same source directory, so replacing it here makes the current code
# available at runtime without rerunning Buildout.
COPY src /plone/instance/src

# Migration runners change frequently too; keep them after Buildout as well.
COPY tools /plone/instance/tools

RUN mkdir -p /plone/instance/var/filestorage /plone/instance/var/blobstorage \
    && chown -R 1000:1000 /plone/instance

USER 1000:1000
EXPOSE 8070

CMD ["bin/instance", "fg"]
