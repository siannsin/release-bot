import os


basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
    GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
    SITE_URL = os.environ.get('SITE_URL')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URI', f'sqlite:///{basedir}/data/db.sqlite')
    SQLALCHEMY_ECHO = os.environ.get('SQL_DEBUG', '').lower() in ('true', '1', 't')
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()
    MAX_REPOS_PER_CHAT = int(os.environ.get('MAX_REPOS_PER_CHAT')) if 'MAX_REPOS_PER_CHAT' in os.environ else 0
