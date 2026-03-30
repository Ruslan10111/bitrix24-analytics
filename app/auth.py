"""OAuth2 authentication for Bitrix24 marketplace apps."""

from datetime import datetime, timedelta
import requests
from .models import Portal
from . import db

OAUTH_URL = 'https://oauth.bitrix.info/oauth/token/'


def handle_install(data, app_config):
    """
    Called when Bitrix24 POSTs to /install during app installation.
    Stores the initial tokens for the portal.
    """
    domain = data.get('DOMAIN', '').rstrip('/')
    auth_id = data.get('AUTH_ID', '')
    refresh_id = data.get('REFRESH_ID', '')
    member_id = data.get('member_id', '')
    auth_expires = int(data.get('AUTH_EXPIRES', 3600))

    if not domain or not auth_id:
        return None

    portal = Portal.query.filter_by(domain=domain).first()
    if portal:
        portal.access_token = auth_id
        portal.refresh_token = refresh_id
        portal.member_id = member_id
        portal.expires_at = datetime.utcnow() + timedelta(seconds=auth_expires)
    else:
        portal = Portal(
            domain=domain,
            access_token=auth_id,
            refresh_token=refresh_id,
            member_id=member_id,
            expires_at=datetime.utcnow() + timedelta(seconds=auth_expires),
            installed_at=datetime.utcnow(),
        )
        db.session.add(portal)

    db.session.commit()
    return portal


def refresh_tokens(portal, app_config):
    """Refreshes expired OAuth tokens via Bitrix24 OAuth server."""
    resp = requests.post(OAUTH_URL, data={
        'grant_type': 'refresh_token',
        'client_id': app_config['BITRIX24_CLIENT_ID'],
        'client_secret': app_config['BITRIX24_CLIENT_SECRET'],
        'refresh_token': portal.refresh_token,
    }, timeout=15)

    if resp.status_code != 200:
        return False

    data = resp.json()
    if 'error' in data:
        return False

    portal.access_token = data['access_token']
    portal.refresh_token = data['refresh_token']
    portal.expires_at = datetime.utcnow() + timedelta(seconds=int(data.get('expires_in', 3600)))
    portal.scope = data.get('scope', portal.scope)
    db.session.commit()
    return True


def get_valid_portal(domain, app_config):
    """Returns a portal with a valid (non-expired) access token."""
    portal = Portal.query.filter_by(domain=domain).first()
    if not portal:
        return None
    if portal.is_token_expired():
        if not refresh_tokens(portal, app_config):
            return None
    return portal
