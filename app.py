__version__ = "0.2.4"

import asyncio
from http import HTTPStatus

from flask import Flask, Response, request
from flask_apscheduler import APScheduler
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from github import Github, Auth

from config import Config

db = SQLAlchemy()
migrate = Migrate()
scheduler = APScheduler()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.logger.setLevel(app.config['LOG_LEVEL'])

    db.init_app(app)
    migrate.init_app(app, db)

    scheduler.init_app(app)

    return app


app = create_app()

if app.config['GITHUB_TOKEN']:
    auth = Auth.Token(app.config['GITHUB_TOKEN'])
else:
    auth = None
github_obj = Github(auth=auth)


if app.config['TELEGRAM_BOT_TOKEN']:
    from telegram_bot import TelegramBot

    telegram_bot = TelegramBot(token=app.config['TELEGRAM_BOT_TOKEN'])
    if not asyncio.run(telegram_bot.test_token()):
        app.logger.error('Telegram bot token is invalid')
        exit()
    telegram_bot.start()
else:
    app.logger.error('Telegram bot token not specified')

scheduler.start()


@app.route('/')
async def index():
    bot_me = await telegram_bot.get_me()
    return (f'<a href="https://t.me/{bot_me.username}">{bot_me.first_name}</a> - a telegram bot for GitHub releases.'
            '<br><br>'
            'Source code available at <a href="https://github.com/JanisV/release-bot">release-bot</a>')


@app.post("/telegram")
async def telegram() -> Response:
    """Handle incoming Telegram updates by putting them into the `update_queue`"""
    if app.config['SITE_URL']:
        await telegram_bot.webhook(request.json)
        return Response(status=HTTPStatus.OK)
    else:
        return Response(status=HTTPStatus.NOT_IMPLEMENTED)


if __name__ == '__main__':
    app.run()

import scheduler  # noqa: E402
import models  # noqa: E402
