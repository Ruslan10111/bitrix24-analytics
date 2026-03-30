"""Flask routes — install handler, dashboard, webhook mode."""

from flask import Blueprint, request, redirect, url_for, current_app, Response
from .auth import handle_install, get_valid_portal
from .bitrix_api import BitrixClient
from .analytics import (
    build_user_map, build_stage_map, flatten_deals,
    compute_totals, compute_funnel_dashboard, compute_monthly_dynamics,
    compute_funnel_monthly, compute_manager_analytics, compute_stage_analysis,
    compute_aging, compute_risks, compute_executive_summary,
)
from .dashboard import build_dashboard

bp = Blueprint('main', __name__)


def _build_analytics(client, portal_name=""):
    """Fetch data + compute analytics + render HTML."""
    data = client.fetch_all()

    user_map = build_user_map(data['users'])
    stage_map = build_stage_map(data['all_stages'])
    flat = flatten_deals(data['categories'], data['all_deals'])

    totals = compute_totals(flat)
    funnel_rows = compute_funnel_dashboard(data['categories'], data['all_deals'])
    monthly = compute_monthly_dynamics(flat)
    funnel_monthly = compute_funnel_monthly(data['categories'], data['all_deals'])
    managers = compute_manager_analytics(flat, user_map)
    stages = compute_stage_analysis(data['categories'], data['all_stages'], data['all_deals'])
    aging = compute_aging(data['categories'], data['all_deals'])
    risks = compute_risks(flat, data['activities'])
    summary = compute_executive_summary(
        data['categories'], data['all_deals'], flat, user_map, data['activities']
    )

    html = build_dashboard(
        totals, funnel_rows, monthly, funnel_monthly,
        managers, stages, aging, risks, summary,
        stage_map, user_map, portal_name=portal_name,
    )
    return html


# ─── Bitrix24 Marketplace routes ──────────────────────────────

@bp.route('/install', methods=['GET', 'POST'])
def install():
    """Called by Bitrix24 when admin installs the app."""
    if request.method == 'POST':
        portal = handle_install(request.form, current_app.config)
        if portal:
            return redirect(url_for('main.dashboard_view', DOMAIN=portal.domain))
        return "Installation failed", 400

    return ('<h2>Bitrix24 Analytics</h2>'
            '<p>Установите приложение из маркетплейса Bitrix24.</p>')


@bp.route('/dashboard')
def dashboard_view():
    """Main dashboard — requires DOMAIN param or portal auth."""
    domain = request.args.get('DOMAIN', '')
    if not domain:
        return "Missing DOMAIN parameter", 400

    portal = get_valid_portal(domain, current_app.config)
    if not portal:
        return (f"<h3>Портал {domain} не найден или токен истёк.</h3>"
                "<p>Переустановите приложение из маркетплейса Bitrix24.</p>"), 401

    client = BitrixClient(portal, current_app.config)
    html = _build_analytics(client, portal_name=domain)
    return Response(html, content_type='text/html; charset=utf-8')


@bp.route('/uninstall', methods=['POST'])
def uninstall():
    """Called by Bitrix24 when app is removed."""
    from .models import Portal, CachedData
    from . import db
    domain = request.form.get('DOMAIN', '')
    portal = Portal.query.filter_by(domain=domain).first()
    if portal:
        CachedData.query.filter_by(portal_id=portal.id).delete()
        db.session.delete(portal)
        db.session.commit()
    return "OK"


# ─── Webhook mode (for quick start without OAuth) ────────────

@bp.route('/webhook')
def webhook_dashboard():
    """
    Quick-start mode: use a webhook URL to generate analytics.
    Usage: /webhook?url=https://portal.bitrix24.ru/rest/ID/TOKEN/
    """
    webhook_url = request.args.get('url', '').rstrip('/')
    if not webhook_url:
        return ('<div style="max-width:600px;margin:80px auto;font-family:sans-serif">'
                '<h2>Bitrix24 Analytics — Webhook Mode</h2>'
                '<form action="/webhook" method="get">'
                '<label>Вебхук URL:</label><br>'
                '<input name="url" style="width:100%;padding:10px;margin:10px 0" '
                'placeholder="https://your-portal.bitrix24.ru/rest/ID/TOKEN/"><br>'
                '<button style="padding:10px 30px;background:#2b6cb0;color:#fff;border:none;'
                'border-radius:6px;cursor:pointer;font-size:16px">Построить отчёт</button>'
                '</form></div>')

    # Create a fake portal for webhook mode
    from .models import Portal
    portal = Portal(
        domain='__webhook__',
        access_token='',
        refresh_token='',
    )
    # Override BitrixClient to use webhook URL directly
    client = WebhookClient(webhook_url)
    html = _build_analytics(client, portal_name=webhook_url.split('/')[2])
    return Response(html, content_type='text/html; charset=utf-8')


class WebhookClient:
    """Simplified client for webhook mode (no OAuth, limited scopes)."""

    def __init__(self, webhook_url):
        self.webhook_url = webhook_url.rstrip('/')
        import requests as http_requests
        import time, json
        self._requests = http_requests
        self._time = time
        self._json = json

    def call(self, method, params=None):
        url = f"{self.webhook_url}/{method}"
        for attempt in range(5):
            try:
                r = self._requests.get(url, params=params, timeout=30)
                data = r.json()
                if data.get('error') == 'QUERY_LIMIT_EXCEEDED':
                    self._time.sleep(1)
                    continue
                return data
            except Exception:
                self._time.sleep(2)
        return {'result': []}

    def list_all(self, method, params=None, limit=0):
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
            if nxt is None or len(items) >= total:
                break
            params['start'] = nxt
            self._time.sleep(0.35)
        return items

    def fetch_all(self):
        cats = self.list_all('crm.dealcategory.list')
        if not any(str(c.get('ID')) == '0' for c in cats):
            cats.insert(0, {'ID': '0', 'NAME': 'Общая'})

        all_stages = {}
        for cat in cats:
            cid = str(cat['ID'])
            resp = self.call('crm.dealcategory.stage.list', {'id': cid})
            all_stages[cid] = resp.get('result', [])
            self._time.sleep(0.3)

        all_deals = {}
        for cat in cats:
            cid = str(cat['ID'])
            all_deals[cid] = self.list_all('crm.deal.list', {
                'filter[CATEGORY_ID]': cid,
                'select[0]': 'ID', 'select[1]': 'TITLE',
                'select[2]': 'STAGE_ID', 'select[3]': 'STAGE_SEMANTIC_ID',
                'select[4]': 'CATEGORY_ID', 'select[5]': 'ASSIGNED_BY_ID',
                'select[6]': 'OPPORTUNITY', 'select[7]': 'CURRENCY_ID',
                'select[8]': 'DATE_CREATE', 'select[9]': 'CLOSEDATE',
                'select[10]': 'BEGINDATE', 'select[11]': 'CLOSED',
            })

        # user.get may fail with webhook — graceful fallback
        try:
            test = self.call('user.get', {'start': 0})
            if 'error' in test:
                users = []
            else:
                users = self.list_all('user.get', {'ACTIVE': 'true'})
        except Exception:
            users = []

        activities = self.list_all('crm.activity.list', {
            'filter[OWNER_TYPE_ID]': '2',
            'select[0]': 'ID', 'select[1]': 'OWNER_ID',
            'select[2]': 'TYPE_ID', 'select[3]': 'CREATED',
            'select[4]': 'COMPLETED',
        }, limit=15000)

        return {
            'categories': cats,
            'all_stages': all_stages,
            'all_deals': all_deals,
            'users': users,
            'activities': activities,
        }


# ─── Root and landing ─────────────────────────────────────────

@bp.route('/')
def index():
    domain = request.args.get('DOMAIN', '')
    if domain:
        return redirect(url_for('main.dashboard_view', DOMAIN=domain))

    return ('<div style="max-width:700px;margin:80px auto;font-family:sans-serif;text-align:center">'
            '<h1 style="color:#1a365d">Bitrix24 Analytics</h1>'
            '<p style="color:#718096;font-size:18px">Управленческая аналитика по всем воронкам CRM</p>'
            '<div style="margin:40px 0;display:flex;gap:20px;justify-content:center">'
            '<a href="/webhook" style="padding:14px 30px;background:#2b6cb0;color:#fff;'
            'border-radius:8px;text-decoration:none;font-size:16px">Webhook-режим</a>'
            '<a href="/install" style="padding:14px 30px;background:#38a169;color:#fff;'
            'border-radius:8px;text-decoration:none;font-size:16px">Marketplace</a>'
            '</div>'
            '<p style="color:#a0aec0;font-size:13px">'
            'Webhook — быстрый старт без установки (CRM scope)<br>'
            'Marketplace — полная версия с именами менеджеров (CRM + User scope)'
            '</p></div>')
