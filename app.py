from flask import Flask

from database import init_database

app = Flask(__name__)
db = init_database(app)

import models


@app.route('/')
def hello_world():  # put application's code here
    return 'Hello World!'


if __name__ == '__main__':
    app.run()
