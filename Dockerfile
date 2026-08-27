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
RUN python -m pip install -r requirements.txt

# Stable Plone + major third-party base. Keep this separate from our addon so
# adding/changing application source does not reinstall Plone.
COPY buildout-base.cfg /plone/instance/buildout-base.cfg
RUN buildout -c buildout-base.cfg

# Minimal stable develop package used only while generating the final instance
# scripts. It intentionally does not COPY our real setup.py/source before this
# layer, so Python/ZCML/PT/CSS/JS/setup.py edits cannot invalidate Plone base.
RUN mkdir -p /plone/instance/src/imi.migration/src/imi/migration \
    && printf "from setuptools import setup\nsetup(name='imi.migration', version='0.1.0', packages=['imi','imi.migration'], package_dir={'':'src'})\n" \
       > /plone/instance/src/imi.migration/setup.py \
    && touch /plone/instance/src/imi.migration/src/imi/__init__.py \
    && touch /plone/instance/src/imi.migration/src/imi/migration/__init__.py

# App/runtime dependencies are the only layer expected to change when a new
# Python package is added. Plone eggs from the previous layer remain present.
COPY buildout.cfg /plone/instance/buildout.cfg
RUN buildout -c buildout.cfg

# Frequently-changing application and migration code comes last.
COPY src /plone/instance/src
COPY tools /plone/instance/tools

RUN mkdir -p /plone/instance/var/filestorage /plone/instance/var/blobstorage \
    && chown -R 1000:1000 /plone/instance

USER 1000:1000
EXPOSE 8070

CMD ["bin/instance", "fg"]
