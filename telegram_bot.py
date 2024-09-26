import os

import github
from telegram import ForceReply, Update, LinkPreviewOptions
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from github import Github

from models import Chat, Repo

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')

db_url = os.environ.get('DATABASE_URI', 'sqlite:///data/db.sqlite')
engine = create_engine(db_url, echo=True)


def get_or_create_chat(session, telegram_user):
    chat = session.get(Chat, telegram_user.id)
    if not chat:
        chat = Chat(
            id=telegram_user.id,
            lang=telegram_user.language_code,
        )
        session.add(chat)
        session.commit()

    return chat


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user

    with Session(engine) as session:
        get_or_create_chat(session, user)

    await update.message.reply_html(
        rf"Hi {user.mention_html()}!",
        reply_markup=ForceReply(selective=True),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    await update.message.reply_text("Help!")


async def message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Add GitHub repo"""
    user = update.effective_user
    repo_name = update.message.text

    g = Github()
    try:
        repo = g.get_repo(repo_name)
    except github.GithubException as e:
        await update.message.reply_text("Sorry, I can't find that repo.")
        return

    with Session(engine) as session:
        repo_obj = session.get(Repo, repo.id)
        if not repo_obj:
            repo_obj = Repo(
                id=repo.id,
                full_name=repo.full_name,
                link=repo.html_url,
                current_tag=repo.get_latest_release().tag_name,
                current_release_id=repo.get_latest_release().id,
            )
            session.add(repo_obj)
            session.commit()

        chat = get_or_create_chat(session, user)
        if chat in repo_obj.chats:
            await update.message.reply_html(
                f"GitHub repo <a href='{repo.html_url}'>{repo.full_name}</a> has already been added.",
                link_preview_options=LinkPreviewOptions(url=repo.html_url,
                                                        is_disabled=True,
                                                        # prefer_small_media=True,
                                                        ),
            )
        else:
            repo_obj.chats.append(chat)
            session.commit()

            await update.message.reply_html(
                f"Added GitHub repo: <a href='{repo.html_url}'>{repo.full_name}</a>",
                link_preview_options=LinkPreviewOptions(url=repo.html_url,
                                                        # is_disabled=True,
                                                        prefer_small_media=True,
                                                        ),
            )


def run_telegram_bot() -> None:
    """Start the bot."""
    # Create the Application and pass it your bot's token.
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))

    # on non command i.e message - echo the message on Telegram
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message))

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    run_telegram_bot()
