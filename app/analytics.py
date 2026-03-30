"""Core analytics engine. Pure computation — no API calls, no HTML."""

from datetime import datetime, timedelta
from collections import defaultdict, Counter


def safe(v, default=0):
    if v is None:
        return default
    try:
        return float(v)
    except (ValueError, TypeError):
        return default


def pdate(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.split("+")[0])
    except Exception:
        pass
    try:
        return datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S")
    except Exception:
        return None


def get_months(n=12):
    today = datetime.now()
    ms = []
    for i in range(n - 1, -1, -1):
        dt = today.replace(day=1) - timedelta(days=i * 30)
        ms.append(dt.strftime("%Y-%m"))
    return ms


def _deals_in_month(deals, month, field="DATE_CREATE"):
    return [d for d in deals if (pdate(d.get(field)) or datetime.min).strftime("%Y-%m") == month]


def _won_in_month(deals, month):
    return [d for d in deals if d.get("STAGE_SEMANTIC_ID") == "S"
            and (pdate(d.get("CLOSEDATE")) or datetime.min).strftime("%Y-%m") == month]


def _lost_in_month(deals, month):
    return [d for d in deals if d.get("STAGE_SEMANTIC_ID") == "F"
            and (pdate(d.get("CLOSEDATE")) or datetime.min).strftime("%Y-%m") == month]


def build_user_map(users):
    m = {}
    for u in users:
        uid = str(u.get("ID", ""))
        name = f"{u.get('LAST_NAME', '')} {u.get('NAME', '')}".strip()
        m[uid] = name or f"#{uid}"
    return m


def build_stage_map(all_stages):
    m = {}
    for stages in all_stages.values():
        for s in stages:
            m[s["STATUS_ID"]] = s
    return m


def flatten_deals(categories, all_deals):
    flat = []
    for cat in categories:
        cid = str(cat["ID"])
        cn = cat["NAME"]
        for d in all_deals.get(cid, []):
            d["_cn"] = cn
            d["_cid"] = cid
            flat.append(d)
    return flat


def compute_totals(flat):
    today = datetime.now()
    months = get_months(12)
    cur, prev = months[-1], months[-2]

    total_p = [d for d in flat if d.get("STAGE_SEMANTIC_ID") == "P"]
    total_s = [d for d in flat if d.get("STAGE_SEMANTIC_ID") == "S"]
    total_f = [d for d in flat if d.get("STAGE_SEMANTIC_ID") == "F"]
    overdue = [d for d in total_p if pdate(d.get("CLOSEDATE")) and pdate(d.get("CLOSEDATE")) < today]

    return {
        "total": len(flat),
        "in_progress": len(total_p),
        "won": len(total_s),
        "lost": len(total_f),
        "revenue": sum(safe(d.get("OPPORTUNITY")) for d in total_s),
        "pipeline": sum(safe(d.get("OPPORTUNITY")) for d in total_p),
        "conversion": len(total_s) / (len(total_s) + len(total_f)) if (len(total_s) + len(total_f)) else 0,
        "overdue_count": len(overdue),
        "overdue_sum": sum(safe(d.get("OPPORTUNITY")) for d in overdue),
        "cur_month": cur,
        "prev_month": prev,
        "cur_created": len(_deals_in_month(flat, cur)),
        "prev_created": len(_deals_in_month(flat, prev)),
        "cur_won": len(_won_in_month(flat, cur)),
        "prev_won": len(_won_in_month(flat, prev)),
        "cur_lost": len(_lost_in_month(flat, cur)),
        "prev_lost": len(_lost_in_month(flat, prev)),
        "cur_rev": sum(safe(d.get("OPPORTUNITY")) for d in _won_in_month(flat, cur)),
        "prev_rev": sum(safe(d.get("OPPORTUNITY")) for d in _won_in_month(flat, prev)),
    }


def compute_funnel_dashboard(categories, all_deals):
    months6 = get_months(6)
    cur, prev = months6[-1], months6[-2]
    rows = []

    for cat in categories:
        cid = str(cat["ID"])
        deals = all_deals.get(cid, [])
        if not deals:
            continue
        ip = [d for d in deals if d.get("STAGE_SEMANTIC_ID") == "P"]
        won = [d for d in deals if d.get("STAGE_SEMANTIC_ID") == "S"]
        lost = [d for d in deals if d.get("STAGE_SEMANTIC_ID") == "F"]
        wl = len(won) + len(lost)
        conv = len(won) / wl if wl else 0
        s_ip = sum(safe(d.get("OPPORTUNITY")) for d in ip)
        s_won = sum(safe(d.get("OPPORTUNITY")) for d in won)
        avg = s_won / len(won) if won else 0

        trend = [len(_deals_in_month(deals, m)) for m in months6]

        rows.append({
            "name": cat["NAME"],
            "cid": cid,
            "total": len(deals),
            "in_progress": len(ip),
            "won": len(won),
            "lost": len(lost),
            "conversion": conv,
            "pipeline": s_ip,
            "revenue": s_won,
            "avg_check": avg,
            "cur_created": len(_deals_in_month(deals, cur)),
            "prev_created": len(_deals_in_month(deals, prev)),
            "cur_won": len(_won_in_month(deals, cur)),
            "prev_won": len(_won_in_month(deals, prev)),
            "trend_6m": trend,
        })
    return rows


def compute_monthly_dynamics(flat, months=None):
    if months is None:
        months = get_months(12)
    rows = []
    for m in months:
        cr = len(_deals_in_month(flat, m))
        wo = _won_in_month(flat, m)
        lo = len(_lost_in_month(flat, m))
        rv = sum(safe(d.get("OPPORTUNITY")) for d in wo)
        rows.append({"month": m, "created": cr, "won": len(wo), "lost": lo, "revenue": rv})
    return rows


def compute_funnel_monthly(categories, all_deals, months=None):
    """Monthly dynamics per funnel."""
    if months is None:
        months = get_months(6)
    result = {}
    for cat in categories:
        cid = str(cat["ID"])
        deals = all_deals.get(cid, [])
        if len(deals) < 10:
            continue
        rows = []
        for m in months:
            cr = len(_deals_in_month(deals, m))
            wo = _won_in_month(deals, m)
            lo = len(_lost_in_month(deals, m))
            rv = sum(safe(d.get("OPPORTUNITY")) for d in wo)
            rows.append({"month": m, "created": cr, "won": len(wo), "lost": lo, "revenue": rv})
        result[cat["NAME"]] = {"cid": cid, "total": len(deals), "months": rows}
    return result


def compute_manager_analytics(flat, user_map):
    today = datetime.now()
    months = get_months(12)
    cur, prev = months[-1], months[-2]

    mgr = defaultdict(lambda: {
        "t": 0, "w": 0, "l": 0, "p": 0, "rev": 0, "pipe": 0,
        "cur_w": 0, "prev_w": 0, "cur_cr": 0, "prev_cr": 0, "funnels": set()
    })
    for d in flat:
        mid = str(d.get("ASSIGNED_BY_ID", ""))
        m = mgr[mid]
        m["t"] += 1
        m["funnels"].add(d.get("_cn", ""))
        opp = safe(d.get("OPPORTUNITY"))
        sem = d.get("STAGE_SEMANTIC_ID", "")
        if sem == "S":
            m["w"] += 1; m["rev"] += opp
        elif sem == "F":
            m["l"] += 1
        else:
            m["p"] += 1; m["pipe"] += opp
        dc = pdate(d.get("DATE_CREATE"))
        dcl = pdate(d.get("CLOSEDATE"))
        if dc and dc.strftime("%Y-%m") == cur:
            m["cur_cr"] += 1
        if dc and dc.strftime("%Y-%m") == prev:
            m["prev_cr"] += 1
        if sem == "S" and dcl:
            if dcl.strftime("%Y-%m") == cur:
                m["cur_w"] += 1
            if dcl.strftime("%Y-%m") == prev:
                m["prev_w"] += 1

    rows = []
    for mid, s in mgr.items():
        cl = s["w"] + s["l"]
        rows.append({
            "id": mid,
            "name": user_map.get(mid, f"#{mid}"),
            "total": s["t"],
            "won": s["w"],
            "lost": s["l"],
            "in_progress": s["p"],
            "conversion": s["w"] / cl if cl else 0,
            "revenue": s["rev"],
            "pipeline": s["pipe"],
            "cur_won": s["cur_w"],
            "prev_won": s["prev_w"],
            "cur_created": s["cur_cr"],
            "prev_created": s["prev_cr"],
            "funnels": sorted(s["funnels"]),
        })
    rows.sort(key=lambda x: -x["revenue"])
    return rows


def compute_stage_analysis(categories, all_stages, all_deals):
    today = datetime.now()
    result = []
    for cat in categories:
        cid = str(cat["ID"])
        deals = all_deals.get(cid, [])
        stages = all_stages.get(cid, [])
        if not deals or not stages:
            continue
        total_f = len(deals)
        sorted_stages = sorted(stages, key=lambda s: int(s.get("SORT", 0)))
        prev_cnt = total_f
        stage_rows = []
        for stg in sorted_stages:
            sid = stg["STATUS_ID"]
            sd = [d for d in deals if d.get("STAGE_ID") == sid]
            cnt = len(sd)
            sm = sum(safe(d.get("OPPORTUNITY")) for d in sd)
            pct = cnt / total_f if total_f else 0
            ages = [(today - pdate(d.get("DATE_CREATE"))).days for d in sd if pdate(d.get("DATE_CREATE"))]
            avg_age = sum(ages) / len(ages) if ages else 0

            drop = 0
            if prev_cnt > 0 and cnt < prev_cnt:
                drop = (prev_cnt - cnt) / prev_cnt

            stage_rows.append({
                "name": stg["NAME"],
                "status_id": sid,
                "count": cnt,
                "sum": sm,
                "pct": pct,
                "avg_age": avg_age,
                "drop_off": drop,
                "is_won": "WON" in sid,
                "is_lost": "LOSE" in sid,
            })
            if cnt > 0:
                prev_cnt = cnt

        result.append({
            "funnel_name": cat["NAME"],
            "cid": cid,
            "total": total_f,
            "stages": stage_rows,
        })
    return result


def compute_aging(categories, all_deals):
    today = datetime.now()
    rows = []
    for cat in categories:
        cid = str(cat["ID"])
        deals_p = [d for d in all_deals.get(cid, []) if d.get("STAGE_SEMANTIC_ID") == "P"]
        if not deals_p:
            continue
        ages = [(today - pdate(d.get("DATE_CREATE"))).days if pdate(d.get("DATE_CREATE")) else 999 for d in deals_p]
        buckets = [
            sum(1 for a in ages if a < 30),
            sum(1 for a in ages if 30 <= a < 90),
            sum(1 for a in ages if 90 <= a < 180),
            sum(1 for a in ages if 180 <= a < 365),
            sum(1 for a in ages if a >= 365),
        ]
        overdue_s = sum(safe(d.get("OPPORTUNITY")) for d in deals_p
                        if pdate(d.get("CLOSEDATE")) and pdate(d.get("CLOSEDATE")) < today)
        rows.append({
            "funnel": cat["NAME"],
            "total_ip": len(deals_p),
            "buckets": buckets,
            "avg_age": sum(ages) / len(ages),
            "overdue_sum": overdue_s,
        })
    return rows


def compute_risks(flat, activities):
    today = datetime.now()
    act_by_deal = defaultdict(list)
    for a in activities:
        act_by_deal[str(a.get("OWNER_ID", ""))].append(a)

    risk = []
    for d in flat:
        if d.get("STAGE_SEMANTIC_ID") != "P":
            continue
        did = str(d.get("ID", ""))
        acts = act_by_deal.get(did, [])
        if acts:
            last = max(pdate(a.get("CREATED")) or datetime.min for a in acts)
            idle = (today - last).days
        else:
            dt = pdate(d.get("DATE_CREATE"))
            idle = (today - dt).days if dt else 999
        if idle > 30:
            risk.append({
                "title": d.get("TITLE", ""),
                "funnel": d.get("_cn", ""),
                "idle_days": idle,
                "amount": safe(d.get("OPPORTUNITY")),
                "manager_id": str(d.get("ASSIGNED_BY_ID", "")),
            })
    risk.sort(key=lambda x: -x["amount"])

    overdue = []
    for d in flat:
        if d.get("STAGE_SEMANTIC_ID") != "P":
            continue
        dcl = pdate(d.get("CLOSEDATE"))
        if dcl and dcl < today:
            overdue.append({
                "title": d.get("TITLE", ""),
                "funnel": d.get("_cn", ""),
                "overdue_days": (today - dcl).days,
                "amount": safe(d.get("OPPORTUNITY")),
            })
    overdue.sort(key=lambda x: -x["amount"])

    return {"risk_idle": risk, "risk_overdue": overdue}


def compute_stage_month_matrix(categories, all_stages, all_deals, n_months=12):
    """
    For each funnel: matrix of Month × Stage with deal counts.
    Shows: deals created in month M whose current stage is S,
           AND deals closed (won/lost) in month M.
    """
    months = get_months(n_months)
    result = []

    for cat in categories:
        cid = str(cat["ID"])
        deals = all_deals.get(cid, [])
        stages = all_stages.get(cid, [])
        if len(deals) < 10 or not stages:
            continue

        sorted_stages = sorted(stages, key=lambda s: int(s.get("SORT", 0)))
        stage_names = {s["STATUS_ID"]: s["NAME"] for s in sorted_stages}
        stage_order = [s["NAME"] for s in sorted_stages]

        # Matrix: created deals by month × current stage
        created_matrix = defaultdict(lambda: defaultdict(int))
        # Matrix: closed deals by CLOSEDATE month × final stage
        closed_matrix = defaultdict(lambda: defaultdict(int))
        # Totals per month
        month_totals_created = defaultdict(int)
        month_totals_closed = defaultdict(int)

        for d in deals:
            sid = d.get("STAGE_ID", "")
            sname = stage_names.get(sid, sid)
            sem = d.get("STAGE_SEMANTIC_ID", "")
            dc = pdate(d.get("DATE_CREATE"))
            dcl = pdate(d.get("CLOSEDATE"))

            # Created in month → current stage
            if dc:
                m = dc.strftime("%Y-%m")
                if m in months:
                    created_matrix[m][sname] += 1
                    month_totals_created[m] += 1

            # Closed in month (S or F) by CLOSEDATE
            if sem in ("S", "F") and dcl:
                m = dcl.strftime("%Y-%m")
                if m in months:
                    closed_matrix[m][sname] += 1
                    month_totals_closed[m] += 1

        # Find active stages (that have at least some deals)
        active_stages = []
        for sn in stage_order:
            has_data = any(created_matrix[m].get(sn, 0) > 0 or closed_matrix[m].get(sn, 0) > 0
                          for m in months)
            if has_data:
                active_stages.append(sn)

        # Build month rows
        month_rows = []
        for m in months:
            created_by_stage = {sn: created_matrix[m].get(sn, 0) for sn in active_stages}
            closed_by_stage = {sn: closed_matrix[m].get(sn, 0) for sn in active_stages}
            month_rows.append({
                "month": m,
                "created_total": month_totals_created.get(m, 0),
                "closed_total": month_totals_closed.get(m, 0),
                "created_by_stage": created_by_stage,
                "closed_by_stage": closed_by_stage,
            })

        result.append({
            "funnel_name": cat["NAME"],
            "cid": cid,
            "total": len(deals),
            "stages": active_stages,
            "months": month_rows,
        })

    return result


def compute_executive_summary(categories, all_deals, flat, user_map, activities):
    """Top-level summary: strengths, problems, recommendations."""
    # Top funnels by conversion
    top_conv = []
    for cat in categories:
        cid = str(cat["ID"])
        deals = all_deals.get(cid, [])
        won = len([d for d in deals if d.get("STAGE_SEMANTIC_ID") == "S"])
        lost = len([d for d in deals if d.get("STAGE_SEMANTIC_ID") == "F"])
        wl = won + lost
        if wl >= 10:
            top_conv.append({"name": cat["NAME"], "conv": won / wl, "won": won, "closed": wl})
    top_conv.sort(key=lambda x: -x["conv"])

    # Top funnels by revenue
    top_rev = []
    for cat in categories:
        cid = str(cat["ID"])
        deals = all_deals.get(cid, [])
        won = [d for d in deals if d.get("STAGE_SEMANTIC_ID") == "S"]
        rv = sum(safe(d.get("OPPORTUNITY")) for d in won)
        top_rev.append({"name": cat["NAME"], "revenue": rv, "total": len(deals)})
    top_rev.sort(key=lambda x: -x["revenue"])

    # Top managers
    mgr = defaultdict(lambda: {"w": 0, "l": 0, "rev": 0})
    for d in flat:
        mid = str(d.get("ASSIGNED_BY_ID", ""))
        if d.get("STAGE_SEMANTIC_ID") == "S":
            mgr[mid]["w"] += 1
            mgr[mid]["rev"] += safe(d.get("OPPORTUNITY"))
        elif d.get("STAGE_SEMANTIC_ID") == "F":
            mgr[mid]["l"] += 1
    top_mgr = []
    for mid, s in mgr.items():
        cl = s["w"] + s["l"]
        if cl >= 10:
            top_mgr.append({
                "name": user_map.get(mid, f"#{mid}"),
                "conv": s["w"] / cl, "won": s["w"], "closed": cl, "revenue": s["rev"],
            })
    top_mgr.sort(key=lambda x: -x["revenue"])

    return {
        "top_conv_funnels": top_conv[:5],
        "top_rev_funnels": top_rev[:5],
        "top_managers": top_mgr[:5],
        "low_conv_funnels": [f for f in top_conv if f["conv"] < 0.15],
    }
