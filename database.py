import os

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate


def init_database(app):
    db_url = os.environ.get('DATABASE_URI', f'sqlite:///{app.root_path}/data/db.sqlite')
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url

    db = SQLAlchemy(app)
    Migrate(app, db)

    return db
