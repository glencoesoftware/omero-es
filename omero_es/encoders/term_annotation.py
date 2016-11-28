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

Class, Encoder = omero_marshal.encode.encoders.term_annotation.encoder


class InvariantTagAnnotationEncoder(Encoder):

    def encode(self, obj):
        v = super(Encoder, self).encode(obj)
        self.set_if_not_none(v, 'TermValue', obj.termValue)
        return v

omero_marshal.ENCODERS[Class] = \
    InvariantTagAnnotationEncoder(omero_marshal._ctx)
