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
import math
import sys
import time

from pprint import pformat

from mx.DateTime import gmtime

import omero.clients
assert omero.clients

from omero import UnloadedEntityException
from omero.sys import ParametersI
from omero_marshal import get_encoder

# Override various `omero_marshal` encoders with our own
import omero_es.encoders


# Package scoped logger
log = logging.getLogger(__name__)


QUERY_IMAGE_COUNTS = """SELECT dataset.id, count(d_i_link.id)
FROM Project AS project
JOIN project.datasetLinks AS p_d_link
JOIN p_d_link.child AS dataset
JOIN dataset.imageLinks as d_i_link
WHERE project.id = :id
GROUP BY dataset.id
"""

QUERY_IMAGES = """SELECT image FROM Image AS image
LEFT OUTER JOIN FETCH image.annotationLinks AS i_a_link
LEFT OUTER JOIN FETCH i_a_link.child
JOIN FETCH image.pixels AS pixels
JOIN FETCH pixels.channels AS channel
JOIN FETCH channel.logicalChannel
JOIN FETCH image.datasetLinks AS i_d_link
JOIN i_d_link.parent AS dataset
WHERE dataset.id = :id
"""

QUERY_WELLS = """SELECT well FROM Well AS well
LEFT OUTER JOIN FETCH well.annotationLinks AS w_a_link
LEFT OUTER JOIN FETCH w_a_link.child
LEFT OUTER JOIN FETCH well.wellSamples as wellsample
LEFT OUTER JOIN FETCH wellsample.image as image
LEFT OUTER JOIN FETCH image.annotationLinks as i_a_link
LEFT OUTER JOIN FETCH i_a_link.child
LEFT OUTER JOIN FETCH image.pixels AS pixels
LEFT OUTER JOIN FETCH pixels.channels AS channel
LEFT OUTER JOIN FETCH channel.logicalChannel
JOIN well.plate AS plate
WHERE plate.id = :id
"""


def usage(error=None):
    """
    Prints usage so that we don't have to. :)
    """
    cmd = sys.argv[0]
    if error:
        print error
    print """Usage:
  %(cmd)s <options> <project_id ...>

Creates an Elasticsearch document for a Project hierarchy

Options:
  -s                  server hostname
  -p                  server port
  -u                  username
  -w                  password
  -a                  create documents for all Projects
  -h                  display this help and exit
  --url               Elasticsearch base URL to save documents into
  --debug             turn debugging on
  --index             index to write into (default: 'dv')

Examples:
    %(cmd)s -s localhost -p 4064 -u jsmith -w secret 1

Report bugs to support@glencoesoftware.com""" % {'cmd': cmd}
    sys.exit(2)


class BaseDocument(object):

    def __init__(self, client):
        self.client = client

    def __str__(self):
        return json.dumps(self.document, sort_keys=True, indent=2)

    def unload_annotation_details(self, obj):
        if obj.isAnnotationLinksLoaded():
            for annotation_link in obj.copyAnnotationLinks():
                annotation_link.child.unloadDetails()


class ImageDocument(BaseDocument):

    def __init__(self, client, image, dataset_id):
        super(ImageDocument, self).__init__(client)
        self.dataset_id = dataset_id
        self.image = image
        self.document = self.encode_image(image)

    def encode_image(self, obj):
        if obj.isPixelsLoaded() and obj.sizeOfPixels() > 0:
            pixels = obj.getPrimaryPixels()
            pixels.unloadDetails()
            if pixels.isChannelsLoaded() and pixels.sizeOfChannels() > 0:
                for channel in pixels.copyChannels():
                    channel.unloadDetails()
                    self.unload_annotation_details(channel)
        self.unload_annotation_details(obj)

        encoder = get_encoder(obj.__class__)
        v = encoder.encode(obj)
        return v


class ProjectDocument(BaseDocument):

    def __init__(self, client, project):
        super(ProjectDocument, self).__init__(client)
        self.project = project
        self.document = self.encode_project(project)

    def encode_project(self, obj):
        obj.details.owner.unloadDetails()
        obj.details.group.unloadDetails()
        for _map in obj.details.group.copyGroupExperimenterMap():
            _map.child.unloadDetails()
        if obj.isDatasetLinksLoaded() and obj.sizeOfDatasetLinks() > 0:
            for dataset_link in obj.copyDatasetLinks():
                dataset = dataset_link.child
                dataset.unloadDetails()
                self.unload_annotation_details(dataset)
        self.unload_annotation_details(obj)

        encoder = get_encoder(obj.__class__)
        v = encoder.encode(obj)
        return v

    def get_image_counts_per_dataset(self, query_service):
        params = ParametersI()
        params.addId(self.project.id.val)
        t0 = time.time()
        image_counts = dict([
            (r[0].val, r[1].val) for r in query_service.projection(
                QUERY_IMAGE_COUNTS, params, {'omero.group': '-1'}
            )
        ])
        log.info(
            'Image counts: %s (%dms)' % (
                pformat(image_counts, indent=2),
                (time.time() - t0) * 1000
            )
        )
        return image_counts

    def find_images(self):
        session = self.client.getSession()
        query_service = session.getQueryService()
        dataset_ids = [v.id.val for v in self.project.linkedDatasetList()]

        image_counts_per_dataset = self.get_image_counts_per_dataset(
            query_service
        )

        for dataset_id in dataset_ids:
            if image_counts_per_dataset.get(dataset_id, 0) < 1:
                log.info(
                    'Skipping Dataset:%d Project:%d, contains no Images!' % (
                        dataset_id, self.project.id.val
                    )
                )
                continue

            offset = 0
            count = limit = 100
            params = ParametersI().addId(dataset_id).page(offset, limit)
            while count == limit:
                t0 = time.time()
                images = query_service.findAllByQuery(
                    QUERY_IMAGES, params, {'omero.group': '-1'}
                )
                log.info(
                    'Found %d Images in Dataset:%d Project:%d (%dms)' % (
                        len(images), dataset_id, self.project.id.val,
                        (time.time() - t0) * 1000
                    )
                )
                count = len(images)
                offset += count
                params.page(offset, limit)
                for image in images:
                    yield image

    @property
    def images(self):
        try:
            return sum([
                v.linkedImageList() for v in self.project.linkedDatasetList()
            ], list())
        except UnloadedEntityException:
            return self.find_images()

    @property
    def image_documents(self):
        for image in self.images:
            for dataset_link in image.copyDatasetLinks():
                yield ImageDocument(
                    self.client, image, dataset_link.parent.id.val
                )


class PlateDocument(BaseDocument):

    def __init__(self, client, plate):
        super(PlateDocument, self).__init__(client)
        self.plate = plate
        self.document = self.encode_plate(plate)

    def encode_plate(self, obj):
        obj.details.owner.unloadDetails()
        obj.details.group.unloadDetails()
        for _map in obj.details.group.copyGroupExperimenterMap():
            _map.child.unloadDetails()
        if obj.isScreenLinksLoaded() and obj.sizeOfScreenLinks() > 0:
            for screen_link in obj.copyScreenLinks():
                screen = screen_link.parent
                screen.unloadDetails()
                self.unload_annotation_details(screen)
        self.unload_annotation_details(obj)

        encoder = get_encoder(obj.__class__)
        v = encoder.encode(obj)
        return v

    def find_wells(self):
        session = self.client.getSession()
        query_service = session.getQueryService()
        offset = 0
        count = limit = 100
        params = ParametersI().addId(self.plate.id.val).page(offset, limit)
        while count == limit:
            t0 = time.time()
            wells = query_service.findAllByQuery(
                QUERY_WELLS, params, {'omero.group': '-1'}
            )
            log.info(
                'Found %d Wells in Plate:%d (%dms)' % (
                    len(wells), self.plate.id.val,
                    (time.time() - t0) * 1000
                )
            )
            count = len(wells)
            offset += count
            params.page(offset, limit)
            for well in wells:
                yield well

    @property
    def wells(self):
        try:
            return self.plate.copyWells()
        except UnloadedEntityException:
            return self.find_wells()

    @property
    def well_documents(self):
        for well in self.wells:
            yield WellDocument(
                self.client, well
            )


class WellDocument(ImageDocument):

    def __init__(self, client, well):
        self.client = client
        self.well = well
        self.document = self.encode_well(well)

    def encode_well(self, obj):
        obj.unloadDetails()
        if obj.isWellSamplesLoaded() and obj.sizeOfWellSamples() > 0:
            for wellsample in obj.copyWellSamples():
                wellsample.unloadDetails()
                image = wellsample.image
                if image is not None and image.isLoaded():
                    image.unloadDetails()
                    self.unload_annotation_details(image)
                    if image.isPixelsLoaded():
                        pixels = image.getPrimaryPixels()
                        pixels.unloadDetails()
                        if pixels.isChannelsLoaded():
                            for channel in pixels.copyChannels():
                                channel.unloadDetails()
                                self.unload_annotation_details(channel)
        self.unload_annotation_details(obj)

        encoder = get_encoder(obj.__class__)
        v = encoder.encode(obj)
        return v
