"""Database models for portal tokens and cached data."""

from datetime import datetime
from . import db


class Portal(db.Model):
    """Stores OAuth2 tokens per Bitrix24 portal."""
    __tablename__ = 'portals'

    id = db.Column(db.Integer, primary_key=True)
    domain = db.Column(db.String(255), unique=True, index=True, nullable=False)
    member_id = db.Column(db.String(64), index=True)
    access_token = db.Column(db.String(512), nullable=False)
    refresh_token = db.Column(db.String(512), nullable=False)
    expires_at = db.Column(db.DateTime)
    scope = db.Column(db.String(512), default='crm,user')
    installed_by = db.Column(db.Integer)
    installed_at = db.Column(db.DateTime, default=datetime.utcnow)

    def is_token_expired(self):
        if not self.expires_at:
            return True
        return datetime.utcnow() >= self.expires_at


class CachedData(db.Model):
    """Caches API responses per portal (TTL = 1 hour)."""
    __tablename__ = 'cached_data'

    id = db.Column(db.Integer, primary_key=True)
    portal_id = db.Column(db.Integer, db.ForeignKey('portals.id'), nullable=False)
    data_key = db.Column(db.String(128), nullable=False)  # e.g. "categories", "deals_3"
    data_json = db.Column(db.Text, nullable=False)
    fetched_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('portal_id', 'data_key', name='uix_portal_key'),
    )

    def is_fresh(self, ttl_seconds=3600):
        if not self.fetched_at:
            return False
        age = (datetime.utcnow() - self.fetched_at).total_seconds()
        return age < ttl_seconds
