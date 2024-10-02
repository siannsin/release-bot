# release-bot - a Telegram bot that notifies you of new GitHub releases

This is a Telegram bot that monitors the releases of given repos, sending messages upon a new release.

If you don't need a local installation you can use public bot, avalaible at https://t.me/janisreleasebot.

## Alternatives
This bot is inspired by [new(releases)](https://newreleases.io/) and [release-bot](https://github.com/chofnar/release-bot).

## Features
- Ready for selfhosting, has docker image
- Work locally, without white IP and domain name
- Only Telegram token requred

## Commands
`/start` - show welcome message  
`/about` - information about this bot  
`/list` - show your subscription  
`/editlist` - show and edit your subscription  
`/stats` - show server statistics  

## Running it yourself

### With docker
Using docker compose:
```
services:
  container_name: release-bot
  image: ghcr.io/janisv/release-bot:latest
  restart: unless-stopped
  environment:
    - TELEGRAM_BOT_TOKEN=<telegram_token>
    #- GITHUB_TOKEN=<github_token> # optional
  ports:
    - 5000:5000
  volumes:
    - /path/to/data:/app/data
```

or docker run:
`docker run -p 5000:5000 -e TELEGRAM_BOT_TOKEN="<telegram_token>" -v /path/to/data:/app/data -d --name release-bot ghcr.io/janisv/release-bot:latest`

### From source
Look at Development section

### Set the necessary env vars
`TELEGRAM_BOT_TOKEN` - get this from [BotFather](https://t.me/botfather). You'll need to create a bot.

`GITHUB_TOKEN` - (optional) GitHub personal access token (classic) or fine-grained personal access token. When not specified working well for about 20 repos. More info at [Rate limits for the REST API](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api?apiVersion=2022-11-28).

## Development
Setup env vars and run:

    pip3 install -r requirements.txt
    flask db upgrade
    python ./telegram_bot.py &
    python ./release-bot.py
