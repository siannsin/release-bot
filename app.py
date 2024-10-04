__version__ = "0.1.3"

import asyncio
import re

import github
import telegram
from flask import Flask
from flask_apscheduler import APScheduler
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from github import Github, Auth
from telegram.constants import MessageLimit

from config import Config

github_extra_html_tags_pattern = re.compile("<p align=\".*\".*>|</p>|<a name=\".*\">|</a>|<picture>.*</picture>|"
                                            "<sub>|</sub>|<sup>|</sup>|<!--.*-->")
github_img_html_tag_pattern = re.compile("<img src=\"(.*?)\".*>")

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

import models
from telegram_bot import TelegramBot

telegram_bot = TelegramBot(token=app.config['TELEGRAM_BOT_TOKEN'])
if not telegram_bot.test_token():
    app.logger.error('Telegram bot token is invalid')
    exit()

scheduler.start()
telegram_bot.start()


@scheduler.task('interval', id='poll_github', hours=1)
def poll_github():
    with (scheduler.app.app_context()):
        for repo_obj in models.Repo.query.all():
            try:
                app.logger.info('Poll GitHub repo %s', repo_obj.full_name)
                repo = github_obj.get_repo(repo_obj.id)
            except github.GithubException as e:
                print("Github Exception in poll_github", e)
                continue

            try:
                release = repo.get_latest_release()
            except github.GithubException as e:
                # Repo has no releases yet
                continue

            if repo_obj.current_release_id != release.id:
                repo_obj.current_release_id = release.id
                repo_obj.current_tag = release.tag_name
                db.session.commit()

                release_body = release.body
                release_body = github_extra_html_tags_pattern.sub(
                    "",
                    release_body
                )
                release_body = github_img_html_tag_pattern.sub(
                    "\\1",
                    release_body
                )
                release_body = release_body[:MessageLimit.MAX_TEXT_LENGTH]

                message = (f"<a href='{repo.html_url}'>{repo.full_name}</a>:\n"
                           f"<b>{release.title}</b>"
                           f" <code>{release.tag_name}</code>"
                           f"{" <i>pre-release</i>" if release.prerelease else ""}\n"
                           f"<blockquote>{release_body}</blockquote>"
                           f"<a href='{release.html_url}'>release note...</a>")

                for chat in repo_obj.chats:
                    try:
                        asyncio.run(telegram_bot.send_message(chat_id=chat.id,
                                                              text=message,
                                                              parse_mode='HTML',
                                                              disable_web_page_preview=True))
                    except telegram.error.Forbidden as e:
                        app.logger.info('Bot was blocked by the user')
                        # TODO: Delete empty repos
                        db.session.delete(chat)
                        db.session.commit()


@app.route('/')
async def index():
    bot_me = await telegram_bot.get_me()
    return (f'<a href="https://t.me/{bot_me.username}">{bot_me.first_name}</a> - a telegram bot for GitHub releases.'
            '<br><br>'
            'Source code available at <a href="https://github.com/JanisV/release-bot">release-bot</a>')


if __name__ == '__main__':
    app.run()
