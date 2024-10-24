import asyncio
import re

import github
import telegram
from telegram.constants import ParseMode, MessageLimit
from telegramify_markdown import markdownify

from app import models
from app import github_obj, db, telegram_bot, scheduler

PROCESS_PRE_RELEASES = False

github_extra_html_tags_pattern = re.compile("<p align=\".*?\".*?>|</p>|<a name=\".*?\">|</a>|<picture>.*?</picture>|"
                                            "</?h[1-4]>|</?sub>|</?sup>|</?details>|</?summary>|</?b>|</?dl>|</?dt>|"
                                            "</?dd>|</?em>|<!--.*?-->",
                                            flags=re.DOTALL)
github_img_html_tag_pattern = re.compile("<img .*?src=\"(.*?)\".*?>")


def format_release_message(chat, repo, release):
    release_body = release.body
    release_body = github_extra_html_tags_pattern.sub(
        "",
        release_body
    )
    release_body = github_img_html_tag_pattern.sub(
        "\\1",
        release_body
    )
    if len(release_body) > MessageLimit.MAX_TEXT_LENGTH - 256:
        release_body = f"{release_body[:MessageLimit.MAX_TEXT_LENGTH - 256]}\n-=SKIPPED=-"

    current_tag = release.tag_name
    if (release.title == current_tag or
            release.title == f"v{current_tag}" or
            f"v{release.title}" == current_tag):
        # Skip release title when it is equal to tag
        release_title = ""
    else:
        release_title = release.title

    if chat.release_note_format == "quote":
        message = (f"<a href='{repo.html_url}'>{repo.full_name}</a>:\n"
                   f"<b>{release_title}</b>"
                   f" <code>{current_tag}</code>"
                   f"{" <i>pre-release</i>" if release.prerelease else ""}\n"
                   f"<blockquote>{release_body}</blockquote>"
                   f"<a href='{release.html_url}'>release note...</a>")
    elif chat.release_note_format == "pre":
        message = (f"<a href='{repo.html_url}'>{repo.full_name}</a>:\n"
                   f"<b>{release_title}</b>"
                   f" <code>{current_tag}</code>"
                   f"{" <i>pre-release</i>" if release.prerelease else ""}\n"
                   f"<pre>{release_body}</pre>"
                   f"<a href='{release.html_url}'>release note...</a>")
    else:
        message = markdownify(f"[{repo.full_name}]({repo.html_url})\n"
                              f"{f"*{release_title}*" if release_title else ""}"
                              f" `{current_tag}`"
                              f"{" _pre-release_" if release.prerelease else ""}\n\n"
                              f"{release_body + "\n\n" if release_body else ""}"
                              f"[release note...]({release.html_url})")

    return message


@scheduler.task('cron', id='poll_github', hour='*')
def poll_github():
    with scheduler.app.app_context():
        for repo_obj in models.Repo.query.all():
            #  TODO: Use sqlalchemy_utils.auto_delete_orphans
            if repo_obj.is_orphan():
                scheduler.app.logger.info(f"Delete orphaned GitHub repo {repo_obj.full_name}")
                db.session.delete(repo_obj)
                db.session.commit()
                continue

            try:
                scheduler.app.logger.info(f"Poll GitHub repo {repo_obj.full_name}")
                repo = github_obj.get_repo(repo_obj.id)
            except github.UnknownObjectException as e:
                message = f"GitHub repo {repo_obj.full_name} has been deleted"

                for chat in repo_obj.chats:
                    try:
                        asyncio.run(telegram_bot.send_message(chat_id=chat.id,
                                                              text=message,
                                                              disable_web_page_preview=True))
                    except telegram.error.Forbidden as e:
                        pass

                scheduler.app.logger.info(f"Delete deleted GitHub repo {repo_obj.full_name}")
                db.session.delete(repo_obj)
                db.session.commit()
                continue
            except github.GithubException as e:
                scheduler.app.logger.error(f"GithubException for {repo_obj.full_name} in poll_github: {e}")
                continue

            has_release = False
            has_tag = False
            try:
                if PROCESS_PRE_RELEASES:
                    if repo.get_releases().totalCount > 0:
                        release = repo.get_releases()[0]
                else:
                    release = repo.get_latest_release()
                has_release = True
            except github.GithubException as e:
                # Repo has no releases yet
                if repo.get_tags().totalCount > 0:
                    tag = repo.get_tags()[0]
                    has_tag = True

            if has_release and repo_obj.current_release_id != release.id:
                repo_obj.current_release_id = release.id
                repo_obj.current_tag = release.tag_name
                db.session.commit()

                for chat in repo_obj.chats:
                    message = format_release_message(chat, repo, release)

                    if chat.release_note_format in ("quote", "pre"):
                        parse_mode = ParseMode.HTML
                    else:
                        parse_mode = ParseMode.MARKDOWN_V2

                    try:
                        asyncio.run(telegram_bot.send_message(chat_id=chat.id,
                                                              text=message,
                                                              parse_mode=parse_mode,
                                                              disable_web_page_preview=True))
                    except telegram.error.Forbidden as e:
                        scheduler.app.logger.info('Bot was blocked by the user')
                        db.session.delete(chat)
                        db.session.commit()
            elif has_tag and repo_obj.current_tag != tag.name:
                repo_obj.current_tag = tag.name
                db.session.commit()

                # TODO: Use tag.message as release_body text
                message = (f"<a href='{repo.html_url}'>{repo.full_name}</a>:\n"
                           f"<code>{repo_obj.current_tag}</code>")

                for chat in repo_obj.chats:
                    try:
                        asyncio.run(telegram_bot.send_message(chat_id=chat.id,
                                                              text=message,
                                                              parse_mode=ParseMode.HTML,
                                                              disable_web_page_preview=True))
                    except telegram.error.Forbidden as e:
                        scheduler.app.logger.info('Bot was blocked by the user')
                        db.session.delete(chat)
                        db.session.commit()


@scheduler.task('cron', id='poll_github_user', hour='*/8')
def poll_github_user():
    with scheduler.app.app_context():
        for chat in models.Chat.query.filter(models.Chat.github_username.is_not(None)).all():
            try:
                github_user = github_obj.get_user(chat.github_username)
            except github.GithubException as e:
                scheduler.app.logger.error(f"Can't found user '{chat.github_username}'")
                continue

            try:
                asyncio.run(telegram_bot.add_starred_repos(chat, github_user, telegram_bot))
            except telegram.error.Forbidden as e:
                scheduler.app.logger.info('Bot was blocked by the user')
                db.session.delete(chat)
                db.session.commit()
