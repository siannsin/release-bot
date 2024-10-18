from datetime import datetime, timezone

from app import db


def aware_utcnow():
    return datetime.now(timezone.utc)


class Chat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lang = db.Column(db.String(2), default='en')
    github_username = db.Column(db.String)
    release_note_format = db.Column(db.String)
    created_at = db.Column(db.DateTime, default=aware_utcnow)

    repos = db.relationship('Repo', secondary='chat_repo', back_populates='chats')


class Repo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String)
    description = db.Column(db.String)
    link = db.Column(db.String)
    current_tag = db.Column(db.String)
    current_release_id = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=aware_utcnow)

    chats = db.relationship('Chat', secondary='chat_repo', back_populates='repos')

    def is_orphan(self):
        # TODO: Use SQL COUNT instead Python len
        return len(self.chats) == 0


class ChatRepo(db.Model):
    chat_id = db.Column(db.Integer, db.ForeignKey('chat.id'), primary_key=True)
    repo_id = db.Column(db.Integer, db.ForeignKey('repo.id'), primary_key=True)
