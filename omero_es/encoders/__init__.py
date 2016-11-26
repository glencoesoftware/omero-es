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

# Needed for `omero.RType`
import omero.clients

from . import boolean_annotation, \
	comment_annotation, \
	double_annotation, \
	long_annotation, \
	map_annotation, \
	tag_annotation, \
	term_annotation, \
	text_annotation, \
	timestamp_annotation, \
	xml_annotation \
