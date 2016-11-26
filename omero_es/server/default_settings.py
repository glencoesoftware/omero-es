# The secret key
SECRET_KEY = 'super-secret'

# Log file
LOG_FILE = None

# Log format
LOG_FORMAT = '%(asctime)s %(levelname)-7s [%(name)16s] %(message)s'

# Log level
LOG_LEVEL = 10

# OMERO.web session engine ('database' or 'redis')
OMERO_WEB_SESSION_ENGINE = 'database'

# OMERO.web cache key prefix
# https://docs.djangoproject.com/en/1.8/topics/cache/#cache-key-prefixing
OMERO_WEB_CACHE_KEY_PREFIX = ''

# OMERO.web cache version
# https://docs.djangoproject.com/en/1.8/topics/cache/#cache-versioning
OMERO_WEB_CACHE_VERSION = 1

# http://flask-sqlalchemy.pocoo.org/2.1/config/
SQLALCHEMY_TRACK_MODIFICATIONS = False

# Elasticsearch base URI
ELASTICSEARCH_URI = 'http://localhost:9200'

# Elasticsearch index to search against
ELASTICSEARCH_INDEX = 'omero'
