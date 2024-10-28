import github

from app.models import Release, Repo

PROCESS_PRE_RELEASES = False


def store_latest_release(session, repo, repo_obj):
    has_release = False
    has_tag = False
    try:
        if PROCESS_PRE_RELEASES:
            if repo.get_releases().totalCount > 0:
                release = repo.get_releases()[0]
                has_release = True
        else:
            release = repo.get_latest_release()
            has_release = True
    except github.GithubException as e:
        # Repo has no releases yet
        if repo.get_tags().totalCount > 0:
            tag = repo.get_tags()[0]
            has_tag = True

    if has_release:
        release_obj = session.query(Release).join(Repo) \
            .filter(Repo.id == repo_obj.id).filter(Release.release_id == release.id) \
            .first()
        if not release_obj:
            release_obj = Release(
                release_id=release.id,
                tag_name=release.tag_name,
                release_date=release.published_at,
                link=release.html_url,
            )
            repo_obj.releases.append(release_obj)
            session.commit()

            return release
    elif has_tag:
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
            return tag

    return None
