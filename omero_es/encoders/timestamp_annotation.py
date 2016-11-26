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

Class, Encoder = omero_marshal.encode.encoders.timestamp_annotation.encoder


class InvariantTimestampAnnotationEncoder(Encoder):

    def encode(self, obj):
        v = super(InvariantTimestampAnnotationEncoder, self).encode(obj)
        self.set_if_not_none(v, 'Value', obj.timeValue)
        return v

omero_marshal.ENCODERS[Class] = \
    InvariantTimestampAnnotationEncoder(omero_marshal._ctx)
