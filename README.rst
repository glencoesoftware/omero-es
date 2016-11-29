OMERO Elasticsearch
===================

OMERO Elasticsearch utilities and search server endpoint for OMERO.web.

Requirements
============

* OMERO 5.2.x+
* Elasticsearch 5+
* Python 2.6+

Workflow
========

The utilities and search server endpoint for OMERO.web rely on the following workflow:

1. Setup of OMERO.web to use database or Redis backed sessions

1. Application of Elasticsearch document mappings for `omero-marshal` marshalled OMERO model objects

1. Manual indexing of OMERO

1. Running the search server endpoint for OMERO.web

1. Redirecting your OMERO.web installation to use the search server endpoint

Development Installation
========================

1. Clone the repository::

        git clone git@github.com:glencoesoftware/omero-es.git

1. Set up a virtualenv (http://www.pip-installer.org/) and activate it::

        curl -O -k https://raw.github.com/pypa/virtualenv/master/virtualenv.py
        python virtualenv.py omero-es-virtualenv
        source omero-es-virtualenv/bin/activate
        pip install -r requirements.txt
        pip install -r requirements-dev.txt

Applying Document Mappings
==========================

If at any point you need to start document mappings or re-index you can
always remove the entire index by executing::

    curl -X DELETE http://localhost:9200/omero

The document mappings for Project-Dataset, Image, Plate and Well can be
applied (the order is important; child mappings have to be created before
parent mappings) as follows::

    # Assuming the index has not yet been created
    curl -X PUT http://localhost:9200/omero
    curl -X PUT -d '@mapping_image.json' http://localhost:9200/omero/_mapping/image
    curl -X PUT -d '@mapping_well.json' http://localhost:9200/omero/_mapping/well
    curl -X PUT -d '@mapping_project.json' http://localhost:9200/omero/_mapping/project
    curl -X PUT -d '@mapping_plate.json' http://localhost:9200/omero/_mapping/plate

Manual Indexing
===============

Once you have `omero-es` installed you can perform manual indexing of
all or part of the data in your OMERO server.  You can also just dump the
JSON that would be saved to Elasticsearch.

* Dumping JSON that would be saved for a single Project::

    python -m omero_es.index -s server -p port -u username -w password \
        --project 1

* Indexing a single Project::

    python -m omero_es.index -s server -p port -u username -w password \
        --url http://localhost:9200 --project 1

* Indexing all data (Project-Dataset-Image and Screen-Plate-Well)::

    python -m omero_es.index -s server -p port -u username -w password \
        --url http://localhost:9200 -a

Configuring and Running the Server
==================================

The search server endpoint piggybacks on the OMERO.web Django
session.  As such it is essential that as a prerequisite to running the
server that your OMERO.web instance be configured to use either database
or Redis backed sessions.  Filesystem backed sessions **are not** supported.

1. Configure the application (http://flask.pocoo.org/docs/0.11/config/#instance-folders)::

        # If in development mode
        mkdir instance/
        cp settings.cfg.example instance/settings.cfg
        ...

        # If running from a virtualenv
        mkdir -p path/to/virtualenv/var/instance
        cp settings.cfg.example path/to/virtualenv/var/settings.cfg
        ...

1. Start the server::

        python omero_es/manage.py runserver

Redirecting OMERO.web to the Server
===================================

What follows are two snippets which can be placed in your nginx configuration
for OMERO.web to redirect searches to the search server endpoint::

    upstream es-backend {
        server 127.0.0.1:5000 fail_timeout=0 max_fails=0;
        server 127.0.0.1:5001 fail_timeout=0 max_fails=0;
    }

    ...

    location /webclient/load_searching/ {
        proxy_pass http://es-backend/search/;
    }

Running Scripts
===============

Various management scripts have been written with `Flask-Script` to allow
administration functions to be performed on the command line.  You can
inspect the available scripts::

    python omero_es/manage.py --help

Running Tests
=============

Using py.test to run the unit tests::

    py.test tests/unit/

Reference
=========
