import asyncio
import os

import github
import telegram
from flask import Flask
from flask_apscheduler import APScheduler
from github import Github, Auth

from database import init_database

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')

app = Flask(__name__)
app.logger.setLevel('INFO')
db = init_database(app)

scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()

import models

GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
if GITHUB_TOKEN:
    auth = Auth.Token(GITHUB_TOKEN)
    github_obj = Github(auth=auth)
else:
    github_obj = Github()


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
                    bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)    # TODO: Use single bot instance
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
def hello_world():  # put application's code here
    return 'Hello World!'


if __name__ == '__main__':
    app.run()
