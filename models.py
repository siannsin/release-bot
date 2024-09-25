from datetime import datetime, timezone

from app import db


def aware_utcnow():
    return datetime.now(timezone.utc)


class ChatSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lang = db.Column(db.String(2), default='en')
    created_at = db.Column(db.DateTime, default=aware_utcnow)
