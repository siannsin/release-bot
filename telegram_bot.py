import re
from itertools import batched

import github
from telegram import Update, LinkPreviewOptions, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import InlineKeyboardMarkupLimit
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

from app import app, github_obj, __version__
from models import Chat, Repo, ChatRepo

engine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'], echo=app.config['SQLALCHEMY_ECHO'])

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


class TelegramBot(object):
    def __init__(self, token):
        self.application = Application.builder().token(token).build()

        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("about", self.about_command))
        self.application.add_handler(CommandHandler("list", self.list_command))
        self.application.add_handler(CommandHandler("editlist", self.edit_list_command))
        self.application.add_handler(CommandHandler("stats", self.stats_command))
        self.application.add_handler(MessageHandler(filters.COMMAND, self.unknown_command))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.message))
        self.application.add_handler(CallbackQueryHandler(self.button))

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send a message when the command /start is issued."""
        user = update.effective_user

        with Session(engine) as session:
            get_or_create_chat(session, user)

        await update.message.reply_text(
            "Send a message containing repo for subscribing in one of the following formats: "
            "owner/repo, https://github.com/owner/repo"
        )

    async def about_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send a message when the command /about is issued."""
        user = update.effective_user

        await update.message.reply_text(
            f"release-bot - a telegram bot for GitHub releases v{__version__}\n"
            "Source code available at https://github.com/JanisV/release-bot"
        )

    async def list_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send a message when the command /list is issued."""
        user = update.effective_user

        with Session(engine) as session:
            text = "Your subscriptions:\n"
            chat = get_or_create_chat(session, user)
            for i, repo in enumerate(chat.repos):
                text += f"{i + 1}. <b><a href='{repo.link}'>{repo.full_name}</a></b>\n"

        await update.message.reply_html(
            text,
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )

    async def edit_list_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send a message when the command /editlist is issued."""
        user = update.effective_user

        keyboard = []
        with Session(engine) as session:
            chat = get_or_create_chat(session, user)
            for i, repo in enumerate(chat.repos):
                repo_name = repo.full_name.split('/')[1]
                if repo.current_tag:
                    repo_current_tag = repo.current_tag
                    repo_current_tag_url = f"{repo.link}/releases/{repo.current_tag}"
                else:
                    repo_current_tag = "N/A"
                    repo_current_tag_url = f"{repo.link}/releases"
                keyboard.append([InlineKeyboardButton(repo_name, url=repo.link),
                                 InlineKeyboardButton(repo_current_tag, url=repo_current_tag_url),
                                 InlineKeyboardButton("🗑️", callback_data=repo.id)])

        if keyboard:
            btn_per_line = len(keyboard[0])
            for split_keyboard in batched(keyboard, InlineKeyboardMarkupLimit.TOTAL_BUTTON_NUMBER // btn_per_line):
                split_keyboard_list = list(split_keyboard)
                split_keyboard_list.append([InlineKeyboardButton("Cancel", callback_data="cancel")])
                reply_markup = InlineKeyboardMarkup(split_keyboard_list)

                await update.message.reply_text("Here's all your added repos with their releases:",
                                                reply_markup=reply_markup)
        else:
            await update.message.reply_text("You are haven't repos yet.")

    async def button(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send a message when the command /stats is issued."""
        with Session(engine) as session:
            repo_count = session.query(Repo).count()
            user_count = session.query(Chat).count()
            subscription_count = session.query(ChatRepo).count()

            # text = f"I have to update {} releases for {} repos via {} subscriptions added by {} users."
            text = f"I have to update {repo_count} repos via {subscription_count} subscriptions added by {user_count} users."

        await update.message.reply_text(text)

    async def message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
                repo_obj = Repo(
                    id=repo.id,
                    full_name=repo.full_name,
                    link=repo.html_url,
                )
                try:
                    release = repo.get_latest_release()
                    repo_obj.current_tag = release.tag_name
                    repo_obj.current_release_id = release.id
                except github.GithubException as e:
                    # Repo has no releases yet
                    pass

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

                if repo_obj.current_release_id:
                    await update.message.reply_html(
                        f"Added GitHub repo: <a href='{repo.html_url}'>{repo.full_name}</a>",
                        link_preview_options=LinkPreviewOptions(url=repo.html_url,
                                                                # is_disabled=True,
                                                                prefer_small_media=True,
                                                                ),
                    )
                else:
                    await update.message.reply_html(
                        f"Added GitHub repo: <a href='{repo.html_url}'>{repo.full_name}</a>, but it has not releases",
                        link_preview_options=LinkPreviewOptions(url=repo.html_url,
                                                                # is_disabled=True,
                                                                prefer_small_media=True,
                                                                ),
                    )

    async def unknown_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text("Sorry, I don't understand. Please pick one of the valid options.")
        await self.start_command(update, context)

    async def get_me(self, *args, **kwargs):
        async with self.application.bot:
            return await self.application.bot.getMe(*args, **kwargs)

    async def send_message(self, *args, **kwargs):
        async with self.application.bot:
            await self.application.bot.send_message(*args, **kwargs)

    def run_polling(self):
        # Run the bot until the user presses Ctrl-C
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)


def run_telegram_bot() -> None:
    """Start the bot."""
    telegram_bot = TelegramBot(app.config['TELEGRAM_BOT_TOKEN'])
    telegram_bot.run_polling()


if __name__ == '__main__':
    run_telegram_bot()
