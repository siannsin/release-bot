from http import HTTPStatus

from flask import Response, request

from app import telegram_bot, app


@app.route('/')
async def index():
    bot_me = await telegram_bot.get_me()
    return (f'<a href="https://t.me/{bot_me.username}">{bot_me.first_name}</a> - a telegram bot for GitHub releases.'
            '<br><br>'
            'Source code available at <a href="https://github.com/JanisV/release-bot">release-bot</a>')


@app.post("/telegram")
async def telegram() -> Response:
    if app.config['SITE_URL']:
        await telegram_bot.webhook(request.json)
        return Response(status=HTTPStatus.OK)
    else:
        return Response(status=HTTPStatus.NOT_IMPLEMENTED)
