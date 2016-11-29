#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (c) 2016 Glencoe Software, Inc. All rights reserved.
#
# This software is distributed under the terms described by the LICENCE file
# you can find at the root of the distribution bundle.
# If the file is missing please request a copy by contacting
# jason@glencoesoftware.com.
#

import json
import logging
import sys
import time

import omero

from getopt import getopt, GetoptError

from elasticsearch import Elasticsearch, helpers
from omero.sys import ParametersI

from .document import ProjectDocument, PlateDocument

# Package scoped logger
log = logging.getLogger(__name__)

QUERY_ALL_PROJECT_IDS = """SELECT project.id FROM Project AS project"""

QUERY_ALL_SCREEN_IDS = """SELECT screen.id FROM Screen AS screen"""

QUERY_PROJECT = """SELECT project FROM Project AS project
JOIN FETCH project.details.creationEvent as c_event
JOIN FETCH c_event.type
JOIN FETCH project.details.updateEvent as u_event
JOIN FETCH u_event.type
JOIN FETCH project.details.owner
JOIN FETCH project.details.group AS eg
JOIN FETCH eg.groupExperimenterMap AS eg_e_map
JOIN FETCH eg_e_map.child
LEFT OUTER JOIN FETCH project.annotationLinks AS p_a_link
LEFT OUTER JOIN FETCH p_a_link.child
JOIN FETCH project.datasetLinks AS p_d_link
JOIN FETCH p_d_link.child AS dataset
LEFT OUTER JOIN FETCH dataset.annotationLinks AS d_a_link
LEFT OUTER JOIN FETCH d_a_link.child
WHERE project.id = :id
"""

QUERY_PLATES = """SELECT plate FROM Plate AS plate
JOIN FETCH plate.details.creationEvent as c_event
JOIN FETCH c_event.type
JOIN FETCH plate.details.updateEvent as u_event
JOIN FETCH u_event.type
JOIN FETCH plate.details.owner
JOIN FETCH plate.details.group AS eg
JOIN FETCH eg.groupExperimenterMap AS eg_e_map
JOIN FETCH eg_e_map.child
LEFT OUTER JOIN FETCH plate.annotationLinks AS p_a_link
LEFT OUTER JOIN FETCH p_a_link.child
JOIN FETCH plate.screenLinks AS p_s_link
JOIN FETCH p_s_link.parent AS screen
LEFT OUTER JOIN FETCH screen.annotationLinks AS s_a_link
LEFT OUTER JOIN FETCH s_a_link.child
WHERE screen.id = :id
"""


def usage(error=None):
    """
    Prints usage so that we don't have to. :)
    """
    cmd = sys.argv[0]
    if error:
        print error
    print """Usage:
  %(cmd)s <options>

Creates an Elasticsearch document for a container hierarchy

Options:
  -s                  server hostname
  -p                  server port
  -u                  username
  -w                  password
  -a                  create documents for all containers (Project, Screen)
  -h                  display this help and exit
  --screen <id>       create document for Screen hierarchy
  --project <id>      create document for Project hierarchy
  --url               Elasticsearch base URL to save documents into
  --debug             turn debugging on
  --index             index to write into (default: 'dv')

Examples:
    %(cmd)s -s localhost -p 4064 -u jsmith -w secret -a
    %(cmd)s -s localhost -p 4064 -u jsmith -w secret --project 1 --project 2
    %(cmd)s -s localhost -p 4064 -u jsmith -w secret --screen 1 --screen 2
    %(cmd)s -s localhost -p 4064 -u jsmith -w secret --project 1 --screen 2

Report bugs to support@glencoesoftware.com""" % {'cmd': cmd}
    sys.exit(2)


def find_project_ids(client):
    session = client.getSession()
    query_service = session.getQueryService()
    ids = query_service.projection(
        QUERY_ALL_PROJECT_IDS, None, {'omero.group': '-1'}
    )
    ids = [v[0].val for v in ids]
    return ids


def find_screen_ids(client):
    session = client.getSession()
    query_service = session.getQueryService()
    ids = query_service.projection(
        QUERY_ALL_SCREEN_IDS, None, {'omero.group': '-1'}
    )
    ids = [v[0].val for v in ids]
    return ids


def image_document_index_actions(project_document, index):
    for image_document in project_document.image_documents:
        _id = image_document.image.id.val
        if image_document.dataset_id is not None:
            _id = '%d_%d' % (image_document.dataset_id, _id)
        yield {
            '_index': index,
            '_type': 'image',
            '_parent': project_document.project.id.val,
            '_id': _id,
            '_source': json.dumps(image_document.document)
        }


def index_projects(es, index, client, project_ids):
    session = client.getSession()
    query_service = session.getQueryService()

    for project_id in project_ids:
        log.info('Processing Project:%d' % project_id)

        params = ParametersI()
        params.addId(project_id)
        t0 = time.time()
        project = query_service.findByQuery(
            QUERY_PROJECT, params, {'omero.group': '-1'}
        )
        log.info(
            'Loaded Project:%d (%dms)' % (
                project_id, (time.time() - t0) * 1000
            )
        )

        if project is None:
            log.warn('Project:%d has no Datasets or Images!' % project_id)
            continue

        t0 = time.time()
        document = ProjectDocument(client, project)
        log.info(
            'Created document from Project:%d (%dms)' % (
                project_id, (time.time() - t0) * 1000
            )
        )
        if es is None:
            print document
            for image_document in document.image_documents:
                print image_document
            continue

        logging.info('Using Elasticsearch index: %s' % index)

        t0 = time.time()
        result = es.index(
            index=index,
            doc_type='project',
            id=project_id,
            body=json.dumps(document.document)
        )
        log.info(
            'Index complete: %r (%dms)' % (
                result, (time.time() - t0) * 1000
            )
        )

        t0 = time.time()
        result = helpers.bulk(
            es, image_document_index_actions(document, index)
        )
        log.info(
            'Index complete: %r (%dms)' % (
                result, (time.time() - t0) * 1000
            )
        )


def well_document_index_actions(plate_document, index):
    for well_document in plate_document.well_documents:
        yield {
            '_index': index,
            '_type': 'well',
            '_parent': plate_document.plate.id.val,
            '_id': well_document.well.id.val,
            '_source': json.dumps(well_document.document)
        }


def index_screens(es, index, client, screen_ids):
    session = client.getSession()
    query_service = session.getQueryService()

    for screen_id in screen_ids:
        log.info('Processing Screen:%d' % screen_id)

        params = ParametersI()
        params.addId(screen_id)
        t0 = time.time()
        plates = query_service.findAllByQuery(
            QUERY_PLATES, params, {'omero.group': '-1'}
        )
        log.info(
            'Loaded %d Plates from Screen:%d (%dms)' % (
                len(plates), screen_id, (time.time() - t0) * 1000
            )
        )
        for plate in plates:
            plate_id = plate.id.val
            t0 = time.time()
            document = PlateDocument(client, plate)
            log.info(
                'Created document from Plate:%d (%dms)' % (
                    plate_id, (time.time() - t0) * 1000
                )
            )
            if es is None:
                print document
                for well_document in document.well_documents:
                    print well_document
                continue

            logging.info('Using Elasticsearch index: %s' % index)

            t0 = time.time()
            result = es.index(
                index=index,
                doc_type='plate',
                id=plate_id,
                body=json.dumps(document.document)
            )
            log.info(
                'Index complete: %r (%dms)' % (
                    result, (time.time() - t0) * 1000
                )
            )

            t0 = time.time()
            result = helpers.bulk(
                es, well_document_index_actions(document, index)
            )
            log.info(
                'Index complete: %r (%dms)' % (
                    result, (time.time() - t0) * 1000
                )
            )


def main():
    try:
        options, args = getopt(
            sys.argv[1:], "s:p:u:w:a", [
                "debug", "url=", "index=", "screen=", "project="
            ]
        )
    except GetoptError, (msg, _opt):
        usage(msg)

    level = logging.INFO
    server = username = password = None
    port = 4064
    _all = False
    project_ids = list()
    screen_ids = list()
    es = None
    index = 'omero'
    for option, argument in options:
        if option == "-s":
            server = argument
        if option == "-p":
            port = int(argument)
        if option == "-u":
            username = argument
        if option == "-w":
            password = argument
        if option == "-a":
            _all = True
        if option == "--debug":
            level = logging.DEBUG
        if option == "--url":
            es = Elasticsearch([argument], verify_certs=True, timeout=60)
        if option == "--index":
            index = argument
        if option == "--screen":
            screen_ids.append(long(argument))
        if option == "--project":
            project_ids.append(long(argument))

    if _all is False and len(screen_ids) < 1 and len(project_ids) < 1:
        usage('Either -a, Project or Screen hierarchy specification required!')

    format = "%(asctime)s %(levelname)-7s [%(name)16s] %(message)s"
    logging.basicConfig(level=level, format=format)

    client = omero.client(server, port)
    client.createSession(username, password)
    try:

        if _all:
            project_ids = find_project_ids(client)
            screen_ids = find_screen_ids(client)
        log.info('Found %d Projects' % len(project_ids))
        log.info('Found %d Screens' % len(screen_ids))
        index_projects(es, index, client, project_ids)
        index_screens(es, index, client, screen_ids)
    finally:
        client.closeSession()


if __name__ == '__main__':
    main()
