#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (c) 2015 Glencoe Software, Inc. All rights reserved.
#
# This software is distributed under the terms described by the LICENCE file
# you can find at the root of the distribution bundle.
# If the file is missing please request a copy by contacting
# jason@glencoesoftware.com.
#

import omero_marshal

from .text_annotation import InvariantTextAnnotationEncoder
from omero.model import CommentAnnotationI


class InvariantCommentAnnotationEncoder(InvariantTextAnnotationEncoder):

    def encode(self, obj):
        v = super(InvariantCommentAnnotationEncoder, self).encode(obj)
        return v

omero_marshal.ENCODERS[CommentAnnotationI] = \
    InvariantCommentAnnotationEncoder(omero_marshal._ctx)
