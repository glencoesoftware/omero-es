from flask_redis import Redis
from flask_sqlalchemy import SQLAlchemy


# Create database connection object
db = SQLAlchemy()

# Create Redis connection object
redis = Redis()
