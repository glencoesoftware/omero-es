# encoding: utf-8
#
# Copyright (c) 2016 Glencoe Software, Inc. All rights reserved.
#
# This software is distributed under the terms described by the LICENCE file
# you can find at the root of the distribution bundle.
# If the file is missing please request a copy by contacting
# support@glencoesoftware.com.

import logging
import pickle
import time

from flask import Flask, g, jsonify, request

from .core import db, redis
from .models import Session
from .search import search

# Global logger for this package
logger = logging.getLogger(__name__)


def create_app():
    # Create app
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object('omero_es.server.default_settings')
    app.config.from_pyfile('settings.cfg', silent=True)

    session_engine = app.config['OMERO_WEB_SESSION_ENGINE']
    if session_engine == 'database':
        db.init_app(app)
    if session_engine == 'redis':
        redis.init_app(app)

    app.register_blueprint(search)

    def validate_session_database(session_key):
        t0 = time.time()
        session = Session.query.get(session_key)
        logger.info(
            'Session: %r (%dms)' % (session, ((time.time() - t0) * 1000))
        )
        if session is not None:
            g.omero_client = session.login()
            if g.omero_client is not None:
                return True
        return False

    def validate_session_redis(session_key):
        # References (https://github.com/django/django/blob/stable/1.8.x/):
        # * django/contrib/sessions/backends/cache.py
        t0 = time.time()
        key = ':'.join([
            app.config['OMERO_WEB_CACHE_KEY_PREFIX'],
            str(app.config['OMERO_WEB_CACHE_VERSION']),
            '%s%s' % (
                'django.contrib.sessions.cache',
                session_key
            )
        ])
        session_data = redis.get(key)
        logger.info(
            'Session: %r (%dms)' % (key, ((time.time() - t0) * 1000))
        )
        if session_data is not None:
            g.omero_client = Session.do_login(pickle.loads(session_data))
            if g.omero_client is not None:
                return True
        return False

    @app.before_request
    def validate_session():
        session_key = request.cookies.get('sessionid')
        logger.info('Session key: %s' % session_key)
        if session_engine == 'database':
            if validate_session_database(session_key):
                return
        if session_engine == 'redis':
            if validate_session_redis(session_key):
                return
        return jsonify({
            'message': 'Permission denied'
        }), 401

    @app.after_request
    def close_session(response):
        omero_client = g.get('omero_client')
        if omero_client is not None:
            try:
                omero_client.closeSession()
            except:
                logger.debug('Failed to close session', exc_info=True)
        return response

    @app.errorhandler(400)
    def http_400_error_handler(exception):
        app.logger.exception(exception)
        logger.info('HTTP 400: %r, %r' % (exception, exception.__dict__))
        return jsonify(exception.data), 400

    @app.errorhandler(500)
    def http_500_error_handler(exception):
        return exception_handler(exception)

    @app.errorhandler(Exception)
    def exception_handler(exception):
        app.logger.exception(exception)
        return jsonify({
            'message': 'Internal server error'
        }), 500

    filename = app.config['LOG_FILE']
    if filename:
        handler = logging.handlers.WatchedFileHandler(filename)
    else:
        handler = logging.StreamHandler()

    handler.setFormatter(logging.Formatter(app.config['LOG_FORMAT']))
    root_logger = logging.getLogger('')
    root_logger.setLevel(int(app.config['LOG_LEVEL']))
    root_logger.addHandler(handler)

    return app
