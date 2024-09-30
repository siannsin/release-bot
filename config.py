import os


basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
    GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URI', f'sqlite:///{basedir}/data/db.sqlite')
    SQLALCHEMY_ECHO = os.environ.get('SQL_DEBUG', False)
