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

# This file is basically one long set of flake8 errors due to imports of the
# `omero.clients` package which prepares various OMERO classes and monkey
# patch classes for Annotation handling.

# flake8: noqa

# Needed for `omero.RType`
import omero.clients

# noqa: F401
from . import boolean_annotation, \
    comment_annotation, \
    double_annotation, \
    long_annotation, \
    map_annotation, \
    tag_annotation, \
    term_annotation, \
    text_annotation, \
    timestamp_annotation, \
    xml_annotation
