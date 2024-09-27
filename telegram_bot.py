import os
import re

import github
from telegram import ForceReply, Update, LinkPreviewOptions, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from models import Chat, Repo, ChatRepo
from app import github_obj

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')

db_url = os.environ.get('DATABASE_URI', 'sqlite:///data/db.sqlite')
engine = create_engine(db_url, echo=True)

link_pattern = re.compile("https://github.com[:/](.+[:/].+)")
direct_pattern = re.compile(".+/.+")


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


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user

    with Session(engine) as session:
        get_or_create_chat(session, user)

    await update.message.reply_text(
        "Send a message containing repo for subscribing in one of the following formats: "
        "owner/repo, https://github.com/owner/repo"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    await update.message.reply_text("Help!")


async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /list is issued."""
    user = update.effective_user

    with Session(engine) as session:
        text = "Your subscriptions:\n"
        chat = get_or_create_chat(session, user)
        for i, repo in enumerate(chat.repos):
            text += f"{i+1}. <b><a href='{repo.link}'>{repo.full_name}</a></b>\n"

    await update.message.reply_html(
        text,
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )


async def edit_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /editlist is issued."""
    user = update.effective_user

    keyboard = []
    with Session(engine) as session:
        chat = get_or_create_chat(session, user)
        for i, repo in enumerate(chat.repos):
            repo_name = repo.full_name.split('/')[1]
            keyboard.append([InlineKeyboardButton(repo_name, url=repo.link),
                             InlineKeyboardButton(repo.current_tag, url=f"{repo.link}/releases/{repo.current_tag}"),
                             InlineKeyboardButton("🗑️", callback_data=repo.id)])

    keyboard.append([InlineKeyboardButton("Cancel", callback_data="cancel")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text("Here's all your added repos with their releases:", reply_markup=reply_markup)


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    query = update.callback_query

    # CallbackQueries need to be answered, even if no notification to the user is needed
    # Some clients may have trouble otherwise. See https://core.telegram.org/bots/api#callbackquery
    await query.answer()

    if query.data == 'cancel':
        await query.delete_message()
    else:
        with Session(engine) as session:
            chat = get_or_create_chat(session, user)
            repo_obj = session.get(Repo, query.data)
            if repo_obj:
                chat.repos.remove(repo_obj)
                # TODO: Use cascade
                if not repo_obj.chats:
                    session.delete(repo_obj)
                session.commit()

                reply_message = f"Deleted repo: {repo_obj.full_name}"
            else:
                reply_message = "Error: Repo not founded."

        await query.edit_message_text(text=reply_message)


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /stats is issued."""
    with Session(engine) as session:
        repo_count = session.query(Repo).count()
        user_count = session.query(Chat).count()
        subscription_count = session.query(ChatRepo).count()

        # text = f"I have to update {} releases for {} repos via {} subscriptions added by {} users."
        text = f"I have to update {repo_count} repos via {subscription_count} subscriptions added by {user_count} users."

    await update.message.reply_text(text)


async def message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Add GitHub repo"""
    user = update.effective_user

    link_groups = link_pattern.search(update.message.text)
    if link_groups:
        repo_name = link_groups.group(1)
    elif direct_pattern.search(update.message.text):
        repo_name = update.message.text
    else:
        await update.message.reply_text("Error: Invalid repo.")
        return

    try:
        repo = github_obj.get_repo(repo_name)
    except github.GithubException as e:
        await update.message.reply_text("Sorry, I can't find that repo.")
        return

    with Session(engine) as session:
        repo_obj = session.get(Repo, repo.id)
        if not repo_obj:
            release = repo.get_latest_release()
            repo_obj = Repo(
                id=repo.id,
                full_name=repo.full_name,
                link=repo.html_url,
                current_tag=release.tag_name,
                current_release_id=release.id,
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


async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Sorry, I don't understand. Please pick one of the valid options.")
    await start_command(update, context)


def run_telegram_bot() -> None:
    """Start the bot."""
    # Create the Application and pass it your bot's token.
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("list", list_command))
    application.add_handler(CommandHandler("editlist", edit_list_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(MessageHandler(filters.COMMAND, unknown_command))

    application.add_handler(CallbackQueryHandler(button))

    # on non command i.e message - echo the message on Telegram
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message))

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    run_telegram_bot()
