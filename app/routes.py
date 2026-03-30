"""Flask routes — Bitrix24 local app + webhook mode."""

import json
import logging
from flask import Blueprint, request, redirect, url_for, current_app, Response, render_template_string
from .auth import handle_install, get_valid_portal
from .bitrix_api import BitrixClient
from .analytics import (
    build_user_map, build_stage_map, flatten_deals,
    compute_totals, compute_funnel_dashboard, compute_monthly_dynamics,
    compute_funnel_monthly, compute_manager_analytics, compute_stage_analysis,
    compute_aging, compute_risks, compute_executive_summary,
    compute_stage_month_matrix, compute_data_quality, compute_pipeline_health,
)
from .dashboard import build_dashboard

log = logging.getLogger(__name__)
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
    stage_month = compute_stage_month_matrix(data['categories'], data['all_stages'], data['all_deals'])
    aging = compute_aging(data['categories'], data['all_deals'])
    risks = compute_risks(flat, data['activities'])
    dq = compute_data_quality(data['categories'], data['all_deals'], flat)
    ph = compute_pipeline_health(flat)
    summary = compute_executive_summary(
        data['categories'], data['all_deals'], flat, user_map, data['activities']
    )

    html = build_dashboard(
        totals, funnel_rows, monthly, funnel_monthly,
        managers, stages, aging, risks, summary,
        stage_map, user_map,
        stage_month_matrix=stage_month,
        data_quality=dq, pipeline_health=ph,
        portal_name=portal_name,
    )
    return html


# ═══════════════════════════════════════════════════════════════
#  Bitrix24 Local App — install & run inside Bitrix24 iframe
# ═══════════════════════════════════════════════════════════════

# HTML template for Bitrix24 iframe pages (includes BX24 JS SDK)
B24_FRAME = """<!DOCTYPE html><html><head>
<meta charset="UTF-8">
<script src="https://api.bitrix24.com/api/v1/"></script>
<style>
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;margin:0;padding:20px;background:#f5f7fa}
.loading{text-align:center;padding:80px 20px;color:#718096}
.loading .spinner{width:40px;height:40px;border:4px solid #e2e8f0;border-top-color:#2b6cb0;
border-radius:50%;animation:spin 1s linear infinite;margin:0 auto 20px}
@keyframes spin{to{transform:rotate(360deg)}}
.btn{display:inline-block;padding:12px 28px;background:#2b6cb0;color:#fff;border:none;
border-radius:8px;font-size:15px;cursor:pointer;text-decoration:none}
.btn:hover{background:#2c5282}
.btn-green{background:#38a169}.btn-green:hover{background:#2f855a}
.card{background:#fff;border-radius:12px;padding:24px;box-shadow:0 2px 8px rgba(0,0,0,.06);
max-width:600px;margin:40px auto;text-align:center}
h2{color:#1a365d;margin:0 0 12px}
p{color:#718096;line-height:1.6}
.status{margin:16px 0;padding:12px 16px;border-radius:8px;font-size:14px}
.status-ok{background:#c6f6d5;color:#22543d}
.status-err{background:#fed7d7;color:#9b2c2c}
</style></head><body>{{ content|safe }}</body></html>"""


@bp.route('/install', methods=['GET', 'POST'])
def install():
    """
    Main entry point for Bitrix24 local app.
    Bitrix24 always POSTs here when:
     - App is first installed (POST with AUTH_ID)
     - App is opened from left menu (POST with PLACEMENT data)
     - User reopens app (POST with auth params)
    """
    # Server-side install event (POST with AUTH_ID, first install)
    if request.method == 'POST' and request.form.get('AUTH_ID'):
        portal = handle_install(request.form, current_app.config)
        if portal:
            log.info(f"Installed for portal: {portal.domain}")
            content = f"""
            <div class="card">
                <h2>Приложение установлено</h2>
                <p>Портал: <b>{portal.domain}</b></p>
                <div class="status status-ok">Токен получен, приложение готово к работе</div>
                <p style="margin-top:20px">
                    <button class="btn btn-green" onclick="openDashboard()">Открыть аналитику</button>
                </p>
            </div>
            <script>
            BX24.init(function(){{
                BX24.installFinish();
            }});
            function openDashboard() {{
                BX24.openApplication({{
                    'bx24_label': {{'bgColor': 'aqua'}}
                }});
            }}
            </script>"""
            return render_template_string(B24_FRAME, content=content)
        return render_template_string(B24_FRAME, content="""
            <div class="card">
                <h2>Ошибка установки</h2>
                <p>Не удалось получить токен авторизации. Попробуйте переустановить приложение.</p>
            </div>"""), 400

    # POST without AUTH_ID — app opened from left menu / placement
    # or GET — direct access
    # Both cases: render the main app page with BX24 JS SDK
    content = """
    <div class="loading" id="loading">
        <div class="spinner"></div>
        <p>Подключение к Bitrix24...</p>
    </div>
    <div id="error" style="display:none">
        <div class="card">
            <h2>Ошибка подключения</h2>
            <p id="error-msg">Не удалось подключиться к Bitrix24.</p>
            <p style="margin-top:16px">
                <button class="btn" onclick="location.reload()">Попробовать снова</button>
            </p>
        </div>
    </div>
    <div id="dashboard-frame" style="display:none;position:fixed;top:0;left:0;right:0;bottom:0">
        <iframe id="dash-iframe" style="width:100%;height:100%;border:none" src="about:blank"></iframe>
    </div>
    <script>
    BX24.init(function(){
        var auth = BX24.getAuth();
        if (!auth || !auth.access_token) {
            document.getElementById('loading').style.display = 'none';
            document.getElementById('error').style.display = 'block';
            document.getElementById('error-msg').textContent =
                'Не удалось получить токен авторизации. Переустановите приложение.';
            return;
        }

        // Save fresh auth to server, then load dashboard
        fetch('/api/save-auth', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                domain: auth.domain,
                access_token: auth.access_token,
                refresh_token: auth.refresh_token || '',
                member_id: auth.member_id || '',
                expires_in: auth.expires_in || 3600
            })
        })
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data.ok) {
                // Load dashboard directly in iframe
                var iframe = document.getElementById('dash-iframe');
                iframe.src = '/dashboard?DOMAIN=' + encodeURIComponent(auth.domain);
                document.getElementById('loading').style.display = 'none';
                document.getElementById('dashboard-frame').style.display = 'block';
                // Resize parent frame to full height
                BX24.resizeWindow(document.documentElement.scrollWidth, 2000);
            } else {
                throw new Error(data.error || 'save-auth failed');
            }
        })
        .catch(function(err) {
            document.getElementById('loading').style.display = 'none';
            document.getElementById('error').style.display = 'block';
            document.getElementById('error-msg').textContent =
                'Ошибка: ' + err.message;
        });
    });
    </script>"""
    return render_template_string(B24_FRAME, content=content)


@bp.route('/api/save-auth', methods=['POST'])
def save_auth():
    """Save auth token from BX24 JS SDK."""
    data = request.get_json(silent=True) or {}
    from .models import Portal
    from . import db
    from datetime import datetime, timedelta

    domain = data.get('domain', '').rstrip('/')
    access_token = data.get('access_token', '')
    refresh_token = data.get('refresh_token', '')
    member_id = data.get('member_id', '')
    expires_in = int(data.get('expires_in', 3600))

    if not domain or not access_token:
        return {'ok': False, 'error': 'missing data'}, 400

    portal = Portal.query.filter_by(domain=domain).first()
    if portal:
        portal.access_token = access_token
        portal.refresh_token = refresh_token
        portal.member_id = member_id
        portal.expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
    else:
        portal = Portal(
            domain=domain,
            access_token=access_token,
            refresh_token=refresh_token,
            member_id=member_id,
            expires_at=datetime.utcnow() + timedelta(seconds=expires_in),
            installed_at=datetime.utcnow(),
        )
        db.session.add(portal)
    db.session.commit()
    return {'ok': True, 'domain': domain}


@bp.route('/dashboard')
def dashboard_view():
    """Main analytics dashboard."""
    domain = request.args.get('DOMAIN', '')
    if not domain:
        return "Missing DOMAIN parameter", 400

    portal = get_valid_portal(domain, current_app.config)
    if not portal:
        # Try to show re-auth page in iframe
        content = f"""
        <div class="card">
            <h2>🔑 Требуется авторизация</h2>
            <p>Токен для портала <b>{domain}</b> истёк или не найден.</p>
            <p>Откройте приложение из меню Bitrix24 для повторной авторизации.</p>
        </div>"""
        return render_template_string(B24_FRAME, content=content), 401

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


# ═══════════════════════════════════════════════════════════════
#  Webhook mode (standalone, no installation needed)
# ═══════════════════════════════════════════════════════════════

@bp.route('/webhook')
def webhook_dashboard():
    """Quick-start mode via webhook URL."""
    webhook_url = request.args.get('url', '').rstrip('/')
    if not webhook_url:
        return render_template_string(B24_FRAME, content="""
        <div class="card">
            <h2>📊 Webhook-режим</h2>
            <p>Вставьте URL входящего вебхука Bitrix24:</p>
            <form action="/webhook" method="get" style="margin-top:16px">
                <input name="url" style="width:100%;padding:12px;border:2px solid #e2e8f0;
                border-radius:8px;font-size:14px;box-sizing:border-box"
                placeholder="https://your-portal.bitrix24.ru/rest/ID/TOKEN/">
                <p style="margin-top:16px">
                    <button type="submit" class="btn">Построить отчёт</button>
                </p>
            </form>
            <p style="margin-top:16px;font-size:12px;color:#a0aec0">
                Webhook создаётся в Битрикс24 → Разработчикам → Другое → Входящий вебхук
            </p>
        </div>""")

    client = WebhookClient(webhook_url)
    html = _build_analytics(client, portal_name=webhook_url.split('/')[2])
    return Response(html, content_type='text/html; charset=utf-8')


class WebhookClient:
    """Simplified client for webhook mode (no OAuth)."""

    def __init__(self, webhook_url):
        self.webhook_url = webhook_url.rstrip('/')
        import requests as http_requests
        import time
        self._requests = http_requests
        self._time = time

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

        try:
            test = self.call('user.get', {'start': 0})
            users = self.list_all('user.get', {'ACTIVE': 'true'}) if 'error' not in test else []
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


# ═══════════════════════════════════════════════════════════════
#  Landing page
# ═══════════════════════════════════════════════════════════════

@bp.route('/')
def index():
    domain = request.args.get('DOMAIN', '')
    if domain:
        return redirect(url_for('main.dashboard_view', DOMAIN=domain))

    return render_template_string(B24_FRAME, content="""
    <div style="max-width:700px;margin:60px auto;text-align:center">
        <h1 style="color:#1a365d;font-size:32px;margin-bottom:8px">📊 Bitrix24 Analytics</h1>
        <p style="color:#718096;font-size:18px;margin-bottom:40px">
            Управленческая аналитика по всем воронкам CRM
        </p>
        <div style="display:flex;gap:20px;justify-content:center;flex-wrap:wrap">
            <a href="/webhook" class="btn">Webhook-режим</a>
            <a href="/install" class="btn btn-green">Установить в Bitrix24</a>
        </div>
        <div style="margin-top:40px;text-align:left;max-width:500px;margin-left:auto;margin-right:auto">
            <h3 style="color:#2d3748">Что внутри:</h3>
            <ul style="color:#718096;line-height:2">
                <li>Дашборд по воронкам с динамикой MoM</li>
                <li>Аналитика менеджеров с конверсией</li>
                <li>Проект × Месяц × Стадии с графиками</li>
                <li>Drop-off анализ и анализ старения</li>
                <li>Здоровье pipeline и зона рисков</li>
                <li>Executive Summary с планом действий</li>
            </ul>
        </div>
        <p style="color:#a0aec0;font-size:13px;margin-top:30px">
            <b>Webhook</b> — быстрый старт, вставь URL вебхука<br>
            <b>Установить</b> — полная версия внутри Bitrix24 с именами менеджеров
        </p>
    </div>""")
