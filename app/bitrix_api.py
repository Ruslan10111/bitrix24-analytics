"""Bitrix24 REST API client with OAuth2, auto-pagination and rate-limit handling."""

import time
import json
import sys
from datetime import datetime
import requests as http_requests

from .models import Portal, CachedData
from .auth import refresh_tokens
from . import db

PAGE_SIZE = 50
RATE_PAUSE = 0.35


class BitrixClient:
    """OAuth-based Bitrix24 REST API client."""

    def __init__(self, portal: Portal, app_config: dict):
        self.portal = portal
        self.app_config = app_config
        self.base_url = f"https://{portal.domain}/rest"

    def _ensure_token(self):
        if self.portal.is_token_expired():
            refresh_tokens(self.portal, self.app_config)

    def call(self, method, params=None):
        """Single API call with automatic token refresh and rate-limit retry."""
        self._ensure_token()
        url = f"{self.base_url}/{method}"
        params = dict(params or {})
        params['auth'] = self.portal.access_token

        for attempt in range(5):
            try:
                r = http_requests.get(url, params=params, timeout=30)
                data = r.json()

                if data.get('error') == 'expired_token':
                    refresh_tokens(self.portal, self.app_config)
                    params['auth'] = self.portal.access_token
                    continue

                if data.get('error') == 'QUERY_LIMIT_EXCEEDED':
                    time.sleep(1)
                    continue

                return data
            except Exception:
                time.sleep(2)

        return {'result': []}

    def list_all(self, method, params=None, limit=0, progress_cb=None):
        """Auto-paginated list with optional limit."""
        params = dict(params or {})
        params['start'] = 0
        items = []

        while True:
            resp = self.call(method, params)
            chunk = resp.get('result', [])
            if isinstance(chunk, list):
                items.extend(chunk)
            else:
                return chunk

            total = resp.get('total', len(items))
            nxt = resp.get('next')

            if limit and len(items) >= limit:
                return items[:limit]

            if progress_cb:
                progress_cb(method, len(items), total)

            if nxt is None or len(items) >= total:
                break
            params['start'] = nxt
            time.sleep(RATE_PAUSE)

        return items

    # ─── High-level data fetchers ─────────────────────────────

    def _cache_get(self, key):
        """Read from DB cache if fresh."""
        entry = CachedData.query.filter_by(
            portal_id=self.portal.id, data_key=key
        ).first()
        if entry and entry.is_fresh():
            return json.loads(entry.data_json)
        return None

    def _cache_set(self, key, data):
        """Write to DB cache."""
        entry = CachedData.query.filter_by(
            portal_id=self.portal.id, data_key=key
        ).first()
        json_str = json.dumps(data, ensure_ascii=False)
        if entry:
            entry.data_json = json_str
            entry.fetched_at = datetime.utcnow()
        else:
            entry = CachedData(
                portal_id=self.portal.id,
                data_key=key,
                data_json=json_str,
            )
            db.session.add(entry)
        db.session.commit()

    def get_categories(self):
        cached = self._cache_get('categories')
        if cached is not None:
            return cached
        data = self.list_all('crm.dealcategory.list')
        if not any(str(c.get('ID')) == '0' for c in data):
            data.insert(0, {'ID': '0', 'NAME': 'Общая'})
        self._cache_set('categories', data)
        return data

    def get_stages(self, category_id):
        key = f'stages_{category_id}'
        cached = self._cache_get(key)
        if cached is not None:
            return cached
        resp = self.call('crm.dealcategory.stage.list', {'id': category_id})
        data = resp.get('result', [])
        self._cache_set(key, data)
        return data

    def get_deals(self, category_id):
        key = f'deals_{category_id}'
        cached = self._cache_get(key)
        if cached is not None:
            return cached
        data = self.list_all('crm.deal.list', {
            'filter[CATEGORY_ID]': category_id,
            'select[0]': 'ID', 'select[1]': 'TITLE',
            'select[2]': 'STAGE_ID', 'select[3]': 'STAGE_SEMANTIC_ID',
            'select[4]': 'CATEGORY_ID', 'select[5]': 'ASSIGNED_BY_ID',
            'select[6]': 'OPPORTUNITY', 'select[7]': 'CURRENCY_ID',
            'select[8]': 'DATE_CREATE', 'select[9]': 'CLOSEDATE',
            'select[10]': 'BEGINDATE', 'select[11]': 'CLOSED',
        })
        self._cache_set(key, data)
        return data

    def get_users(self):
        """Fetch users — requires 'user' scope (OAuth app, not webhook)."""
        cached = self._cache_get('users')
        if cached is not None:
            return cached
        data = self.list_all('user.get', {'ACTIVE': 'true'})
        if isinstance(data, list):
            self._cache_set('users', data)
            return data
        return []

    def get_activities(self, limit=15000):
        cached = self._cache_get('activities')
        if cached is not None:
            return cached
        data = self.list_all('crm.activity.list', {
            'filter[OWNER_TYPE_ID]': '2',
            'select[0]': 'ID', 'select[1]': 'OWNER_ID',
            'select[2]': 'TYPE_ID', 'select[3]': 'CREATED',
            'select[4]': 'COMPLETED',
        }, limit=limit)
        self._cache_set('activities', data)
        return data

    def fetch_all(self, progress_cb=None):
        """Fetch all data needed for analytics. Returns dict."""
        categories = self.get_categories()
        if progress_cb:
            progress_cb('categories', len(categories), len(categories))

        all_stages = {}
        for cat in categories:
            cid = str(cat['ID'])
            all_stages[cid] = self.get_stages(cid)
            time.sleep(RATE_PAUSE)

        all_deals = {}
        total_deals = 0
        for cat in categories:
            cid = str(cat['ID'])
            deals = self.get_deals(cid)
            all_deals[cid] = deals
            total_deals += len(deals)
            if progress_cb:
                progress_cb(f'deals_{cat["NAME"]}', len(deals), len(deals))

        users = self.get_users()
        activities = self.get_activities()

        return {
            'categories': categories,
            'all_stages': all_stages,
            'all_deals': all_deals,
            'users': users,
            'activities': activities,
            'total_deals': total_deals,
        }
