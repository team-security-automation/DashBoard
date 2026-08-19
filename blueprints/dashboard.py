# -*- coding: utf-8 -*-
from collections import defaultdict, OrderedDict
from datetime import date, timedelta

from flask import Blueprint, render_template
from flask_login import login_required, current_user

from extensions import db
from models import Server, CheckItem, ScanResult, ApprovalRequest, ScoreSnapshot, RISK_LABEL
from scoring import calc_security_level, grade_of, GRADE_COLOR

dashboard_bp = Blueprint("dashboard", __name__)


def _latest_result_map():
    """check_item_id -> {server_id: ScanResult} 형태로 전체 최신 결과를 모은다."""
    servers = Server.query.order_by(Server.id).all()
    per_server = {}
    for srv in servers:
        per_server[srv.id] = {r.check_item_id: r for r in srv.latest_results()}
    return servers, per_server


@dashboard_bp.route("/")
@dashboard_bp.route("/dashboard")
@login_required
def index():
    servers, per_server = _latest_result_map()
    items = CheckItem.query.order_by(CheckItem.order_no).all()

    # --- 서버별 보안점수 ---------------------------------------------------
    server_scores = []
    total_score = 0.0
    for srv in servers:
        results = list(per_server[srv.id].values())
        level, grade, total, identified = calc_security_level(results)
        server_scores.append(dict(server=srv, level=level, grade=grade,
                                   color=GRADE_COLOR.get(grade, "warn")))
        total_score += level
    avg_score = round(total_score / len(servers), 1) if servers else 0.0
    avg_grade = grade_of(avg_score)

    # --- 주간 개선율 (전체 평균 스냅샷 7일 전 대비) --------------------------
    today = date.today()
    week_ago = today - timedelta(days=7)
    snap_today = (ScoreSnapshot.query.filter_by(server_id=None)
                  .filter(ScoreSnapshot.snapshot_date <= today)
                  .order_by(ScoreSnapshot.snapshot_date.desc()).first())
    snap_week = (ScoreSnapshot.query.filter_by(server_id=None)
                 .filter(ScoreSnapshot.snapshot_date <= week_ago)
                 .order_by(ScoreSnapshot.snapshot_date.desc()).first())
    week_delta = None
    if snap_today and snap_week:
        week_delta = round(snap_today.score - snap_week.score, 1)

    # --- 트렌드 스파크라인 데이터 (최근 14일 전체 평균) ---------------------
    trend_rows = (ScoreSnapshot.query.filter_by(server_id=None)
                  .order_by(ScoreSnapshot.snapshot_date).all())
    trend_labels = [r.snapshot_date.strftime("%m/%d") for r in trend_rows]
    trend_values = [r.score for r in trend_rows]

    # --- 위험도 상(H) 미조치 건수, 승인대기 건수 ----------------------------
    critical_open = 0
    vuln_rows = []  # (check_item, server, result) - 취약 항목 전체
    for ci in items:
        for srv in servers:
            r = per_server[srv.id].get(ci.id)
            if r and r.result == "취약":
                vuln_rows.append((ci, srv, r))
                if ci.risk_level == "H":
                    critical_open += 1

    pending_approvals = ApprovalRequest.query.filter_by(status="pending").count()

    # --- 카테고리별 위험 분포 (전체 서버 합산) ------------------------------
    cat_stats = OrderedDict()
    for ci in items:
        cat_stats.setdefault(ci.category, dict(total=0, vuln=0))
    for ci in items:
        for srv in servers:
            r = per_server[srv.id].get(ci.id)
            if not r or r.result == "N/A":
                continue
            cat_stats[ci.category]["total"] += 1
            if r.result == "취약":
                cat_stats[ci.category]["vuln"] += 1
    category_chart = []
    for cat, s in cat_stats.items():
        rate = round((s["vuln"] / s["total"]) * 100, 1) if s["total"] else 0
        compliance = round(100 - rate, 1)
        category_chart.append(dict(category=cat, vuln=s["vuln"], total=s["total"],
                                    vuln_rate=rate, compliance=compliance))

    # --- 위험도 기반 조치 우선순위 큐 (위험도 배점 x 영향받는 서버 수) -------
    grouped = defaultdict(list)
    for ci, srv, r in vuln_rows:
        grouped[ci.id].append((ci, srv, r))
    priority_queue = []
    for ci_id, rows in grouped.items():
        ci = rows[0][0]
        affected = [dict(id=srv.id, hostname=srv.hostname) for _, srv, _ in rows]
        impact = ci.weight * len(rows)
        priority_queue.append(dict(item=ci, affected=affected, count=len(rows), impact=impact))
    priority_queue.sort(key=lambda x: (-x["impact"], -x["item"].weight))
    priority_queue = priority_queue[:10]

    # --- 히트맵 매트릭스 (서버 x 점검항목) ---------------------------------
    heatmap_categories = OrderedDict()
    for ci in items:
        heatmap_categories.setdefault(ci.category, []).append(ci)

    heatmap_rows = []
    for srv in servers:
        cells = []
        for ci in items:
            r = per_server[srv.id].get(ci.id)
            if r is None:
                status = "na"
                label = "N/A"
            elif r.result == "취약":
                status = "vuln"
                label = "취약"
            elif r.result == "N/A":
                status = "na"
                label = "N/A"
            else:
                status = "good"
                label = "양호"
            cells.append(dict(code=ci.code, name=ci.name, risk=ci.risk_level,
                               status=status, label=label))
        heatmap_rows.append(dict(server=srv, cells=cells))

    return render_template(
        "dashboard.html",
        server_scores=server_scores,
        avg_score=avg_score,
        avg_grade=avg_grade,
        avg_color=GRADE_COLOR.get(avg_grade, "warn"),
        week_delta=week_delta,
        trend_labels=trend_labels,
        trend_values=trend_values,
        critical_open=critical_open,
        pending_approvals=pending_approvals,
        server_count=len(servers),
        category_chart=category_chart,
        priority_queue=priority_queue,
        heatmap_categories=heatmap_categories,
        heatmap_rows=heatmap_rows,
        RISK_LABEL=RISK_LABEL,
    )
