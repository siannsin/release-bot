from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate


def init_database(app):
    db = SQLAlchemy(app)
    Migrate(app, db)

    return db
