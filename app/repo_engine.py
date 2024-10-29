import re

import github
from telegram.constants import MessageLimit
from telegramify_markdown import markdownify

from app import app
from app.models import Release, Repo

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


def store_latest_release(session, repo, repo_obj):
    release = None
    prerelease = None
    tag = None

    if app.config['PROCESS_PRE_RELEASES']:
        if repo.get_releases().totalCount > 0:
            prerelease = repo.get_releases()[0]
            if not prerelease.prerelease or prerelease.draft:
                prerelease = None

    try:
        release = repo.get_latest_release()
        if release.draft:
            release = None
    except github.GithubException as e:
        # Repo has no releases yet
        if repo.get_tags().totalCount > 0:
            tag = repo.get_tags()[0]

    if release or prerelease:
        if release:
            release_obj = session.query(Release).join(Repo) \
                .filter(Repo.id == repo_obj.id).filter(Release.release_id == release.id) \
                .first()
            if release_obj:
                if release_obj.pre_release:
                    release_obj.pre_release = release.prerelease
                    session.commit()
                else:
                    release = None
            else:
                release_obj = Release(
                    release_id=release.id,
                    tag_name=release.tag_name,
                    release_date=release.published_at,
                    link=release.html_url,
                    pre_release=release.prerelease,
                )
                repo_obj.releases.append(release_obj)
                session.commit()

        if prerelease:
            release_obj = session.query(Release).join(Repo) \
                .filter(Repo.id == repo_obj.id).filter(Release.release_id == prerelease.id) \
                .first()
            if not release_obj:
                release_obj = Release(
                    release_id=prerelease.id,
                    tag_name=prerelease.tag_name,
                    release_date=prerelease.published_at,
                    link=prerelease.html_url,
                    pre_release=prerelease.prerelease,
                )
                repo_obj.releases.append(release_obj)
                session.commit()
            else:
                prerelease = None

        return release, prerelease
    elif tag:
        release_obj = session.query(Release).join(Repo) \
            .filter(Repo.id == repo_obj.id).filter(Release.tag_name == tag.name) \
            .first()
        if not release_obj:
            release_obj = Release(
                tag_name=tag.name,
                release_date=tag.last_modified_datetime,
            )
            repo_obj.releases.append(release_obj)
            session.commit()
            return tag, None

    return None, None
