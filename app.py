import asyncio

import github
import telegram
from flask import Flask
from flask_apscheduler import APScheduler
from github import Github, Auth

from config import Config
from database import init_database

app = Flask(__name__)
app.config.from_object(Config)
app.logger.setLevel(app.config['LOG_LEVEL'])
db = init_database(app)

scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()

import models

if app.config['GITHUB_TOKEN']:
    auth = Auth.Token(app.config['GITHUB_TOKEN'])
else:
    auth = None
github_obj = Github(auth=auth)


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

            release = repo.get_latest_release()
            if repo_obj.current_release_id != release.id:
                repo_obj.current_release_id = release.id
                repo_obj.current_tag = release.tag_name
                db.session.commit()

                message = (f"<a href='{repo.html_url}'>{repo.full_name}</a>:\n"
                           f"<b>{release.title}</b>"
                           f" <code>{release.tag_name}</code>"
                           f"{" <i>pre-release</i>" if release.prerelease else ""}\n"
                           f"<blockquote>{release.body}</blockquote>"
                           f"<a href='{release.html_url}'>release note...</a>")

                for chat in repo_obj.chats:
                    bot = telegram.Bot(token=app.config['TELEGRAM_BOT_TOKEN'])    # TODO: Use single bot instance
                    try:
                        asyncio.run(bot.send_message(chat_id=chat.id,
                                                     text=message,
                                                     parse_mode='HTML',
                                                     disable_web_page_preview=True))
                    except telegram.error.Forbidden as e:
                        app.logger.info('Bot was blocked by the user')
                        # TODO: Delete empty repos
                        db.session.delete(chat)
                        db.session.commit()


@app.route('/')
def index():
    bot = telegram.Bot(token=app.config['TELEGRAM_BOT_TOKEN'])  # TODO: Use single bot instance
    bot_me = asyncio.run(bot.getMe())
    return (f'<a href="https://t.me/{bot_me.username}">{bot_me.first_name}</a> - a telegram bot for GitHub releases.'
            '<br><br>'
            'Source code available at <a href="https://github.com/JanisV/release-bot">release-bot</a>')


if __name__ == '__main__':
    app.run()
