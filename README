OMERO Elasticsearch
===================

OMERO Elasticsearch utilities and search server endpoint.

Requirements
============

* OMERO 5.2.x+
* Python 2.6+

Development Installation
========================

1. Clone the repository

        git clone git@github.com:glencoesoftware/omero-es.git

2. Set up a virtualenv (http://www.pip-installer.org/) and activate it

        curl -O -k https://raw.github.com/pypa/virtualenv/master/virtualenv.py
        python virtualenv.py omero-es-virtualenv
        source omero-es-virtualenv/bin/activate
        pip install -r requirements.txt
        pip install -r requirements-dev.txt

3. Configure the application

        mkdir instance/
        cp settings.cfg.example instance/settings.cfg
        ...

4. Start the server

        python omero_es/manage.py runserver

Running Scripts
===============

Various management scripts have been written with `Flask-Script` to allow
administration functions to be performed on the command line.  You can
inspect the available scripts:

        python omero_es/manage.py --help

Running Tests
=============

Using py.test to run the unit tests:

    py.test tests/unit/

Reference
=========
