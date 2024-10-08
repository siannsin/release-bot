# release-bot - a Telegram bot that notifies you of new GitHub releases

This is a Telegram bot that monitors the releases of given repos, sending messages upon a new release.

If you don't need a local installation you can use public bot, avalaible at https://t.me/janisreleasebot.

## Alternatives

This bot is inspired by [new(releases)](https://newreleases.io/) and [release-bot](https://github.com/chofnar/release-bot).

## Features

- Ready for self-hosting, has docker image
- Work locally, without white IP and domain name
- Only Telegram token requred
- Rich markdown formatting for release note

## Commands

`/start` - show welcome message  
`/about` - information about this bot  
`/list` - show your subscription  
`/editlist` - show and edit your subscription  
`/starred username` - subscribe to user's starred repos  
`/starred` - unsubscribe from user's starred repos  
`/settings` - change ouput format
`/stats` - show simple server statistics  

## Running it yourself

### With docker

Using docker compose:

```yaml
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

`SITE_URL` - (optional) URL used for listening for incoming requests from the Telegram and GitHub servers. If running locally, you may want to use [localhost.run](https://localhost.run/). When not specified uses polling insted webhooks.

`GITHUB_TOKEN` - (optional) GitHub personal access token (classic) or fine-grained personal access token. When not specified working well for about 20 repos. More info at [Rate limits for the REST API](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api?apiVersion=2022-11-28).

`DATABASE_URI` - (optional) When not specified local SQLite uses.

## Development

Setup env vars and run:

```shell
pip3 install -r requirements.txt
flask db upgrade
python3 -m flask run -h 0.0.0.0
```
