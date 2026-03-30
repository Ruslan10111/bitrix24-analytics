"""HTML dashboard builder. Generates a complete analytics HTML page from computed data."""

from datetime import datetime
from .analytics import safe


def fmt(v):
    if abs(v) >= 1_000_000:
        return f"{v / 1_000_000:,.1f}M ₽"
    if abs(v) >= 1_000:
        return f"{v / 1_000:,.0f}K ₽"
    return f"{v:,.0f} ₽"


def fmtn(v):
    return f"{v:,}".replace(",", " ")


def pct(v):
    return f"{v * 100:.1f}%"


def delta(cur, prev, inverse=False):
    if prev == 0 and cur == 0:
        return '<span class="delta neutral">—</span>'
    if prev == 0:
        return '<span class="delta up">new</span>'
    change = (cur - prev) / prev
    arrow = "↑" if change > 0 else ("↓" if change < 0 else "→")
    if inverse:
        cls = "down" if change > 0.05 else ("up" if change < -0.05 else "neutral")
    else:
        cls = "up" if change > 0.05 else ("down" if change < -0.05 else "neutral")
    return f'<span class="delta {cls}">{arrow} {abs(change) * 100:.0f}%</span>'


def sparkline(values, w=120, h=30):
    if not values or max(values) == 0:
        return ""
    mx = max(values) or 1
    pts = []
    step = w / max(len(values) - 1, 1)
    for i, v in enumerate(values):
        x = i * step
        y = h - (v / mx * h * 0.9) - 1
        pts.append(f"{x:.0f},{y:.1f}")
    color = "#27ae60" if values[-1] >= values[0] else "#e74c3c"
    return (f'<svg width="{w}" height="{h}" style="vertical-align:middle">'
            f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" stroke-width="2"/></svg>')


CSS = """
:root{--blue:#1a365d;--blue2:#2b6cb0;--green:#38a169;--red:#e53e3e;--orange:#dd6b20;
--bg:#f7fafc;--card:#fff;--border:#e2e8f0;--text:#2d3748;--muted:#a0aec0}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',system-ui,sans-serif;
background:var(--bg);color:var(--text);line-height:1.6;font-size:14px}
.wrap{max-width:1500px;margin:0 auto;padding:24px}
header{background:linear-gradient(135deg,#1a365d,#2b6cb0);color:#fff;padding:32px 40px;border-radius:16px;margin-bottom:24px}
header h1{font-size:26px;font-weight:700} header p{opacity:.8;font-size:14px;margin-top:4px}
h2{font-size:18px;font-weight:700;color:var(--blue);margin:28px 0 14px;display:flex;align-items:center;gap:8px}
h2::before{content:'';width:4px;height:22px;background:var(--blue2);border-radius:2px;display:inline-block}
h3{font-size:15px;color:#4a5568;margin:18px 0 8px;font-weight:600}
.kpi-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px;margin:16px 0}
.kpi{background:var(--card);border-radius:12px;padding:18px 20px;box-shadow:0 1px 3px rgba(0,0,0,.06);border:1px solid var(--border)}
.kpi .val{font-size:26px;font-weight:800;color:var(--blue)}
.kpi .label{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.5px;margin-bottom:4px}
.kpi .sub{font-size:12px;color:#718096;margin-top:4px}
.delta{display:inline-block;padding:1px 8px;border-radius:12px;font-size:11px;font-weight:700;margin-left:6px}
.delta.up{background:#c6f6d5;color:#22543d} .delta.down{background:#fed7d7;color:#9b2c2c}
.delta.neutral{background:#e2e8f0;color:#4a5568}
table{width:100%;border-collapse:separate;border-spacing:0;background:var(--card);border-radius:12px;
overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.06);margin:10px 0 20px;border:1px solid var(--border)}
th{background:#edf2f7;color:#4a5568;padding:10px 14px;font-size:12px;text-transform:uppercase;
letter-spacing:.3px;text-align:left;font-weight:700;white-space:nowrap;border-bottom:2px solid var(--border)}
td{padding:9px 14px;font-size:13px;border-bottom:1px solid #f0f0f0}
tr:last-child td{border-bottom:none} tr:hover{background:#f7fafc}
.r{text-align:right} .c{text-align:center} .b{font-weight:700}
.bar-wrap{background:#edf2f7;border-radius:4px;height:20px;position:relative;min-width:60px}
.bar-fill{height:100%;border-radius:4px;min-width:2px}
.bar-label{position:absolute;right:6px;top:2px;font-size:10px;color:#4a5568;font-weight:600}
.card{background:var(--card);border-radius:12px;padding:20px 24px;margin:14px 0;
box-shadow:0 1px 3px rgba(0,0,0,.06);border:1px solid var(--border)}
.card.risk{border-left:4px solid var(--red)} .card.ok{border-left:4px solid var(--green)}
.card.warn{border-left:4px solid var(--orange)}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:16px}
@media(max-width:1000px){.grid2{grid-template-columns:1fr}}
.tg{display:inline-block;padding:2px 8px;border-radius:4px;font-size:12px;font-weight:600}
.tg-g{background:#c6f6d5;color:#22543d} .tg-r{background:#fed7d7;color:#9b2c2c}
.tg-w{background:#fefcbf;color:#744210} .tg-b{background:#bee3f8;color:#2a4365}
.sm{font-size:11px;color:var(--muted)}
ol li,ul li{margin:6px 0;line-height:1.6}
details summary{cursor:pointer;margin:8px 0}
.sep{border:none;border-top:1px solid var(--border);margin:24px 0}
"""


def build_dashboard(totals, funnel_rows, monthly, funnel_monthly,
                    managers, stages, aging, risks, summary,
                    stage_map, user_map, stage_month_matrix=None,
                    portal_name=""):
    """Build complete HTML dashboard. Returns HTML string."""
    today = datetime.now()
    o = []
    h = o.append

    h(f'<!DOCTYPE html><html lang="ru"><head><meta charset="UTF-8">'
      f'<title>Аналитика — {portal_name or "Bitrix24"}</title>'
      f'<style>{CSS}</style></head><body><div class="wrap">')

    # ═══ HEADER ═══
    h(f'<header><h1>Управленческая аналитика</h1>'
      f'<p>{today.strftime("%d.%m.%Y %H:%M")} &bull; {fmtn(totals["total"])} сделок'
      f'{" &bull; " + portal_name if portal_name else ""}</p></header>')

    # ═══ KPI ═══
    t = totals
    h('<div class="kpi-row">')
    kpis = [
        (fmtn(t["total"]), "Всего сделок",
         f'в {t["cur_month"]}: {fmtn(t["cur_created"])}', delta(t["cur_created"], t["prev_created"])),
        (fmtn(t["in_progress"]), "В работе (Pipeline)", fmt(t["pipeline"]), ""),
        (fmtn(t["won"]), "Выиграно",
         f'в {t["cur_month"]}: {fmtn(t["cur_won"])}', delta(t["cur_won"], t["prev_won"])),
        (fmtn(t["lost"]), "Проиграно",
         f'в {t["cur_month"]}: {fmtn(t["cur_lost"])}', delta(t["cur_lost"], t["prev_lost"], inverse=True)),
        (pct(t["conversion"]), "Конверсия", "S/(S+F)", ""),
        (fmt(t["revenue"]), "Выручка",
         f'в {t["cur_month"]}: {fmt(t["cur_rev"])}', delta(t["cur_rev"], t["prev_rev"])),
        (fmt(t["pipeline"]), "Pipeline", f'{fmtn(t["in_progress"])} сделок', ""),
        (f'<span style="color:var(--red)">{fmtn(t["overdue_count"])}</span>',
         "Просрочено", fmt(t["overdue_sum"]), ""),
    ]
    for val, label, sub, badge in kpis:
        h(f'<div class="kpi"><div class="label">{label}</div>'
          f'<div class="val">{val} {badge}</div><div class="sub">{sub}</div></div>')
    h('</div>')

    # ═══ FUNNEL DASHBOARD ═══
    h('<h2>Дашборд по воронкам (с динамикой MoM)</h2>')
    h('<table><tr><th>Воронка</th><th class="r">Всего</th><th class="r">В работе</th>'
      '<th class="r">Выиграно</th><th class="r">Проиграно</th><th class="c">Конверсия</th>'
      '<th class="c">Тренд</th><th class="r">Pipeline</th><th class="r">Выручка</th>'
      '<th class="r">Ср. чек</th><th class="c">Создано MoM</th><th class="c">Выиграно MoM</th></tr>')
    for f_ in funnel_rows:
        cv = f_["conversion"]
        tcls = "tg-g" if cv > 0.5 else ("tg-r" if cv < 0.2 and (f_["won"] + f_["lost"]) > 0 else "tg-w")
        h(f'<tr><td class="b">{f_["name"]}</td><td class="r">{fmtn(f_["total"])}</td>'
          f'<td class="r">{fmtn(f_["in_progress"])}</td><td class="r">{fmtn(f_["won"])}</td>'
          f'<td class="r">{fmtn(f_["lost"])}</td>'
          f'<td class="c"><span class="{tcls}">{pct(cv)}</span></td>'
          f'<td class="c">{sparkline(f_["trend_6m"])}</td>'
          f'<td class="r">{fmt(f_["pipeline"])}</td><td class="r">{fmt(f_["revenue"])}</td>'
          f'<td class="r">{fmt(f_["avg_check"])}</td>'
          f'<td class="c">{fmtn(f_["cur_created"])} {delta(f_["cur_created"], f_["prev_created"])}</td>'
          f'<td class="c">{fmtn(f_["cur_won"])} {delta(f_["cur_won"], f_["prev_won"])}</td></tr>')
    h('</table>')

    # ═══ MONTHLY DYNAMICS ═══
    h('<h2>Динамика по месяцам (12 месяцев)</h2>')
    h('<table><tr><th>Месяц</th><th class="r">Создано</th><th class="c">Δ</th>'
      '<th class="r">Выиграно</th><th class="c">Δ</th><th class="r">Проиграно</th>'
      '<th class="c">Δ</th><th class="r">Выручка</th><th class="c">Δ</th></tr>')
    prev_r = {}
    for i, m in enumerate(monthly):
        bc = delta(m["created"], prev_r.get("created", 0)) if i else ""
        bw = delta(m["won"], prev_r.get("won", 0)) if i else ""
        bl = delta(m["lost"], prev_r.get("lost", 0), inverse=True) if i else ""
        br = delta(m["revenue"], prev_r.get("revenue", 0)) if i else ""
        h(f'<tr><td>{m["month"]}</td><td class="r">{fmtn(m["created"])}</td><td class="c">{bc}</td>'
          f'<td class="r">{fmtn(m["won"])}</td><td class="c">{bw}</td>'
          f'<td class="r">{fmtn(m["lost"])}</td><td class="c">{bl}</td>'
          f'<td class="r">{fmt(m["revenue"])}</td><td class="c">{br}</td></tr>')
        prev_r = m
    h('</table>')

    # Per-funnel monthly
    h('<h3>По воронкам (6 месяцев)</h3>')
    for fn_name, fn_data in funnel_monthly.items():
        h(f'<details><summary class="b">{fn_name} ({fmtn(fn_data["total"])} сделок)</summary>')
        h('<table><tr><th>Месяц</th><th class="r">Создано</th><th class="c">Δ</th>'
          '<th class="r">Выиграно</th><th class="r">Проиграно</th><th class="r">Выручка</th></tr>')
        prev_c = 0
        for i, m in enumerate(fn_data["months"]):
            bd = delta(m["created"], prev_c) if i else ""
            h(f'<tr><td>{m["month"]}</td><td class="r">{fmtn(m["created"])}</td><td class="c">{bd}</td>'
              f'<td class="r">{fmtn(m["won"])}</td><td class="r">{fmtn(m["lost"])}</td>'
              f'<td class="r">{fmt(m["revenue"])}</td></tr>')
            prev_c = m["created"]
        h('</table></details>')

    # ═══ MANAGERS ═══
    h('<h2>Аналитика по менеджерам (с динамикой)</h2>')
    h('<table><tr><th>Менеджер</th><th class="r">Всего</th><th class="r">Выиграно</th>'
      '<th class="r">Проиграно</th><th class="r">В работе</th><th class="c">Конверсия</th>'
      '<th class="r">Выручка</th><th class="r">Pipeline</th>'
      '<th class="c">Выиграно MoM</th><th class="c">Создано MoM</th><th>Воронки</th></tr>')
    for m in managers[:30]:
        cv = m["conversion"]
        tcls = "tg-g" if cv > 0.5 else ("tg-r" if cv < 0.2 and (m["won"] + m["lost"]) >= 5 else "")
        fns = ", ".join(m["funnels"][:3])
        if len(m["funnels"]) > 3:
            fns += f' +{len(m["funnels"]) - 3}'
        h(f'<tr><td class="b">{m["name"]}</td><td class="r">{fmtn(m["total"])}</td>'
          f'<td class="r">{fmtn(m["won"])}</td><td class="r">{fmtn(m["lost"])}</td>'
          f'<td class="r">{fmtn(m["in_progress"])}</td>'
          f'<td class="c"><span class="{tcls}">{pct(cv)}</span></td>'
          f'<td class="r">{fmt(m["revenue"])}</td><td class="r">{fmt(m["pipeline"])}</td>'
          f'<td class="c">{m["cur_won"]} {delta(m["cur_won"], m["prev_won"])}</td>'
          f'<td class="c">{m["cur_created"]} {delta(m["cur_created"], m["prev_created"])}</td>'
          f'<td class="sm">{fns}</td></tr>')
    h('</table>')

    # ═══ STAGES ═══
    h('<h2>Воронки по стадиям (drop-off анализ)</h2>')
    for sec in stages:
        h(f'<details open><summary class="b" style="font-size:15px;color:var(--blue)">'
          f'{sec["funnel_name"]} — {fmtn(sec["total"])} сделок</summary>')
        h('<table><tr><th>Стадия</th><th class="r">Сделок</th><th class="r">Сумма</th>'
          '<th class="r">%</th><th style="min-width:200px">Воронка</th>'
          '<th class="c">Drop-off</th><th class="r">Ср. возраст</th></tr>')
        for st in sec["stages"]:
            bar_w = max(st["pct"] * 100, 0.5)
            bar_c = "#38a169" if st["is_won"] else ("#e53e3e" if st["is_lost"] else "#4299e1")
            drop_h = ""
            if st["drop_off"] > 0.3 and not st["is_won"] and not st["is_lost"]:
                drop_h = f'<span class="tg-r">-{st["drop_off"]*100:.0f}%</span>'
            elif st["drop_off"] > 0:
                drop_h = f'-{st["drop_off"]*100:.0f}%'
            h(f'<tr><td>{st["name"]}</td><td class="r">{fmtn(st["count"])}</td>'
              f'<td class="r">{fmt(st["sum"])}</td><td class="r">{pct(st["pct"])}</td>'
              f'<td><div class="bar-wrap"><div class="bar-fill" style="width:{bar_w}%;background:{bar_c}"></div>'
              f'<div class="bar-label">{st["count"]}</div></div></td>'
              f'<td class="c">{drop_h}</td><td class="r">{st["avg_age"]:.0f}</td></tr>')
        h('</table></details>')

    # ═══ STAGE × MONTH MATRIX ═══
    if stage_month_matrix:
        COLORS = ['#4299e1', '#48bb78', '#ed8936', '#9f7aea', '#f56565',
                  '#38b2ac', '#ecc94b', '#667eea', '#fc8181', '#68d391',
                  '#b794f4', '#fbd38d', '#63b3ed', '#f687b3', '#c6f6d5',
                  '#bee3f8', '#fefcbf', '#e9d8fd']

        h('<h2>Проект × Месяц × Стадии (создано / закрыто)</h2>')

        for sec in stage_month_matrix:
            fn = sec["funnel_name"]
            stg_names = sec["stages"]
            month_rows = sec["months"]
            if not stg_names or not month_rows:
                continue

            h(f'<details><summary class="b" style="font-size:15px;color:var(--blue)">'
              f'{fn} — {fmtn(sec["total"])} сделок, {len(stg_names)} стадий</summary>')

            # ── Table: Created deals by month × stage ──
            h(f'<h3 style="margin-top:14px">Создано сделок (по месяцу создания → текущая стадия)</h3>')
            h('<div style="overflow-x:auto"><table><tr><th>Месяц</th>')
            for sn in stg_names:
                h(f'<th class="c" style="font-size:11px;max-width:90px;white-space:normal">{sn}</th>')
            h('<th class="r b">Итого</th></tr>')

            for mr in month_rows:
                if mr["created_total"] == 0:
                    continue
                h(f'<tr><td class="b">{mr["month"]}</td>')
                for sn in stg_names:
                    v = mr["created_by_stage"].get(sn, 0)
                    style = ' style="background:#ebf8ff;font-weight:700"' if v > 0 else ""
                    h(f'<td class="c"{style}>{v if v else "·"}</td>')
                h(f'<td class="r b">{fmtn(mr["created_total"])}</td></tr>')
            h('</table></div>')

            # ── Table: Closed deals by month × stage ──
            has_closed = any(mr["closed_total"] > 0 for mr in month_rows)
            if has_closed:
                h(f'<h3>Закрыто сделок (по месяцу закрытия → финальная стадия)</h3>')
                # Only show stages that have closed deals
                closed_stages = [sn for sn in stg_names
                                 if any(mr["closed_by_stage"].get(sn, 0) > 0 for mr in month_rows)]
                h('<div style="overflow-x:auto"><table><tr><th>Месяц</th>')
                for sn in closed_stages:
                    h(f'<th class="c" style="font-size:11px;max-width:90px;white-space:normal">{sn}</th>')
                h('<th class="r b">Итого</th></tr>')

                for mr in month_rows:
                    if mr["closed_total"] == 0:
                        continue
                    h(f'<tr><td class="b">{mr["month"]}</td>')
                    for sn in closed_stages:
                        v = mr["closed_by_stage"].get(sn, 0)
                        is_won = "успеш" in sn.lower()
                        is_lost = "провал" in sn.lower()
                        cls = ""
                        if v > 0:
                            if is_won:
                                cls = ' style="background:#c6f6d5;font-weight:700;color:#22543d"'
                            elif is_lost:
                                cls = ' style="background:#fed7d7;font-weight:700;color:#9b2c2c"'
                            else:
                                cls = ' style="background:#ebf8ff;font-weight:700"'
                        h(f'<td class="c"{cls}>{v if v else "·"}</td>')
                    h(f'<td class="r b">{fmtn(mr["closed_total"])}</td></tr>')
                h('</table></div>')

            # ── SVG Stacked Bar Chart: created per month ──
            chart_months = [mr for mr in month_rows if mr["created_total"] > 0]
            if chart_months:
                max_val = max(mr["created_total"] for mr in chart_months)
                if max_val == 0:
                    max_val = 1
                n_months_chart = len(chart_months)
                chart_w = max(n_months_chart * 60, 400)
                chart_h = 280
                bar_area_h = 200
                bar_w = max(chart_w // n_months_chart - 10, 20)
                legend_y = chart_h - 10

                h(f'<h3>График: создано по месяцам × стадия</h3>')
                h(f'<svg width="{chart_w}" height="{chart_h + 60}" '
                  f'style="background:var(--card);border:1px solid var(--border);border-radius:8px;'
                  f'padding:10px;margin:10px 0">')

                # Y-axis labels
                for i in range(5):
                    y_val = max_val * (4 - i) / 4
                    y_pos = 20 + i * (bar_area_h / 4)
                    h(f'<text x="2" y="{y_pos + 4}" font-size="10" fill="#a0aec0">{int(y_val)}</text>')
                    h(f'<line x1="35" y1="{y_pos}" x2="{chart_w}" y2="{y_pos}" '
                      f'stroke="#e2e8f0" stroke-dasharray="3"/>')

                # Bars
                for mi, mr in enumerate(chart_months):
                    x_base = 40 + mi * (chart_w - 50) // n_months_chart
                    y_cursor = 20 + bar_area_h  # bottom of bar area

                    for si, sn in enumerate(stg_names):
                        v = mr["created_by_stage"].get(sn, 0)
                        if v == 0:
                            continue
                        seg_h = (v / max_val) * bar_area_h
                        y_cursor -= seg_h
                        color = COLORS[si % len(COLORS)]
                        h(f'<rect x="{x_base}" y="{y_cursor:.1f}" width="{bar_w}" '
                          f'height="{seg_h:.1f}" fill="{color}" rx="2">'
                          f'<title>{sn}: {v}</title></rect>')

                    # Month label
                    label = mr["month"][5:]  # MM only
                    h(f'<text x="{x_base + bar_w // 2}" y="{20 + bar_area_h + 16}" '
                      f'text-anchor="middle" font-size="11" fill="#4a5568">{label}</text>')
                    # Total on top
                    h(f'<text x="{x_base + bar_w // 2}" y="{20 + bar_area_h - (mr["created_total"] / max_val * bar_area_h) - 4}" '
                      f'text-anchor="middle" font-size="10" fill="#2d3748" font-weight="700">'
                      f'{mr["created_total"]}</text>')

                # Legend (compact, 3 per row)
                legend_x = 40
                legend_row = 0
                for si, sn in enumerate(stg_names[:12]):
                    col = si % 3
                    row = si // 3
                    lx = legend_x + col * (chart_w // 3 - 10)
                    ly = 20 + bar_area_h + 30 + row * 16
                    color = COLORS[si % len(COLORS)]
                    h(f'<rect x="{lx}" y="{ly}" width="10" height="10" fill="{color}" rx="2"/>')
                    h(f'<text x="{lx + 14}" y="{ly + 9}" font-size="10" fill="#4a5568">'
                      f'{sn[:25]}</text>')

                svg_h = 20 + bar_area_h + 30 + ((len(stg_names[:12]) - 1) // 3 + 1) * 16 + 10
                h('</svg>')

            h('</details>')

    # ═══ AGING ═══
    h('<h2>Анализ старения сделок (в работе)</h2>')
    h('<table><tr><th>Воронка</th><th class="r">В работе</th>'
      '<th class="r">&lt;30д</th><th class="r">30-90д</th><th class="r">90-180д</th>'
      '<th class="r">180-365д</th><th class="r">&gt;365д</th>'
      '<th class="r">Ср. возраст</th><th class="r">Просрочено ₽</th></tr>')
    for a in aging:
        h(f'<tr><td class="b">{a["funnel"]}</td><td class="r">{fmtn(a["total_ip"])}</td>')
        for i, b in enumerate(a["buckets"]):
            red = ' style="color:var(--red);font-weight:700"' if b > a["total_ip"] * 0.3 and i >= 3 else ""
            h(f'<td class="r"{red}>{fmtn(b)}</td>')
        h(f'<td class="r">{a["avg_age"]:.0f}</td><td class="r">{fmt(a["overdue_sum"])}</td></tr>')
    h('</table>')

    # ═══ RISKS ═══
    h('<h2>Сделки в зоне риска</h2><div class="grid2">')
    # Overdue
    h('<div class="card risk"><h3>Просроченные (топ по сумме)</h3>')
    h('<table><tr><th>Сделка</th><th>Воронка</th><th class="r">Сумма</th><th class="r">Просрочка</th></tr>')
    for d in risks["risk_overdue"][:15]:
        h(f'<tr><td>{d["title"][:50]}</td><td class="sm">{d["funnel"]}</td>'
          f'<td class="r">{fmt(d["amount"])}</td>'
          f'<td class="r"><span class="tg-r">{d["overdue_days"]} дн</span></td></tr>')
    h(f'</table><p class="sm">Всего: {fmtn(len(risks["risk_overdue"]))} сделок</p></div>')
    # Idle
    h('<div class="card risk"><h3>Без активности &gt;30 дней</h3>')
    h('<table><tr><th>Сделка</th><th>Воронка</th><th class="r">Сумма</th><th class="r">Простой</th></tr>')
    for d in risks["risk_idle"][:15]:
        h(f'<tr><td>{d["title"][:50]}</td><td class="sm">{d["funnel"]}</td>'
          f'<td class="r">{fmt(d["amount"])}</td>'
          f'<td class="r"><span class="tg-w">{d["idle_days"]} дн</span></td></tr>')
    total_risk = sum(d["amount"] for d in risks["risk_idle"])
    h(f'</table><p class="sm">Всего: {fmtn(len(risks["risk_idle"]))} сделок, потенциал {fmt(total_risk)}</p></div>')
    h('</div>')

    # ═══ EXECUTIVE SUMMARY ═══
    h('<h2>Executive Summary</h2><div class="grid2">')
    s = summary
    h('<div class="card ok"><h3>Сильные стороны</h3><ul>')
    for f_ in s["top_conv_funnels"][:3]:
        h(f'<li><b>{f_["name"]}</b> — конверсия {pct(f_["conv"])} ({f_["won"]} из {f_["closed"]})</li>')
    for m in s["top_managers"][:3]:
        h(f'<li><b>{m["name"]}</b> — выручка {fmt(m["revenue"])}, конверсия {pct(m["conv"])}</li>')
    h('</ul></div>')

    h('<div class="card risk"><h3>Проблемные зоны</h3><ul>')
    h(f'<li><b>{fmtn(t["overdue_count"])} просроченных</b> на {fmt(t["overdue_sum"])}</li>')
    for f_ in s["low_conv_funnels"]:
        h(f'<li><b>{f_["name"]}</b> — конверсия {pct(f_["conv"])} ({f_["closed"]} закрытых)</li>')
    h(f'<li><b>{fmtn(len(risks["risk_idle"]))}</b> сделок без активности &gt;30 дн</li>')
    h('</ul></div></div>')

    # Recommendations
    h('<div class="card warn"><h3>Рекомендации</h3><ol>')
    h(f'<li>Аудит {fmtn(t["overdue_count"])} просроченных сделок ({fmt(t["overdue_sum"])})</li>')
    h(f'<li>Активировать {fmtn(len(risks["risk_idle"]))} замерших сделок ({fmt(total_risk)})</li>')
    for f_ in s["low_conv_funnels"][:2]:
        h(f'<li>Разобрать конверсию «{f_["name"]}» ({pct(f_["conv"])})</li>')
    h('<li>Еженедельный разбор дашборда с руководителями</li>')
    h('</ol></div>')

    h(f'<hr class="sep"><p class="sm" style="text-align:center">'
      f'Bitrix24 Analytics &bull; {today.strftime("%d.%m.%Y %H:%M")} &bull; {fmtn(totals["total"])} сделок</p>')
    h('</div></body></html>')
    return "\n".join(o)
