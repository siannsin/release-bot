import github
from flask import Flask
from flask_apscheduler import APScheduler
from github import Github

from database import init_database

app = Flask(__name__)
app.logger.setLevel('INFO')
db = init_database(app)

scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()

import models


@scheduler.task('interval', id='poll_github', hours=1)
def poll_github():
    with (scheduler.app.app_context()):
        g = Github()
        for repo_obj in models.Repo.query.all():
            try:
                app.logger.info('Poll GitHub repo %s', repo_obj.full_name)
                repo = g.get_repo(repo_obj.id)
            except github.GithubException as e:
                print("Github Exception in poll_github", e)
                continue

            if repo_obj.current_release_id != repo.get_latest_release().id:
                repo_obj.current_release_id = repo.get_latest_release().id
                db.session.commit()


@app.route('/')
def hello_world():  # put application's code here
    return 'Hello World!'


if __name__ == '__main__':
    app.run()
