import logging
import pickle
import time

import omero

from base64 import b64decode

from flask import current_app

from .core import db

# Global logger for this package
logger = logging.getLogger(__name__)


class Session(db.Model):
    """
    References (https://github.com/django/django/blob/stable/1.3.x/):
     * django/contrib/sessions/backends/base.py
     * django/contrib/sessions/backends/db.py
     * django/contrib/sessions/models.py
    """
    __tablename__ = 'django_session'

    session_key = db.Column(db.String(40), primary_key=True)
    session_data = db.Column(db.Text)
    expire_date = db.Column(db.DateTime)

    def decode(self):
        hmac, data = b64decode(self.session_data).split(':')
        return pickle.loads(data)

    def login(self):
        self.do_login(self.decode())

    @staticmethod
    def do_login(data):
        connector = data.get('connector')
        if connector is None:
            return None
        omero_client = omero.client(
            current_app.config['OMERO_SERVER'],
            current_app.config['OMERO_PORT']
        )
        t0 = time.time()
        try:
            session = omero_client.joinSession(connector.omero_session_key)
            logger.debug(
                'Login successful, session key: %r (%dms)' % (
                    connector.omero_session_key,
                    ((time.time() - t0) * 1000)
                )
            )
            session.detachOnDestroy()
            return omero_client
        except:
            logger.debug('Joining session failed', exc_info=True)
