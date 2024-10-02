#!/usr/bin/bash

while true; do
    flask db upgrade
    if [[ "$?" == "0" ]]; then
        break
    fi
    echo Deploy command failed, retrying in 5 secs...
    sleep 5
done
export FLASK_APP=release-bot
python3 -m flask run -h 0.0.0.0
