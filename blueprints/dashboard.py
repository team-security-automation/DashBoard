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
    # 수동확인(사람이 판단해야 하는 상태)도 승인 절차로 해소되기 전까지는
    # 취약과 동일하게 "미조치"로 집계한다 (scoring.py의 감점 기준과 일치시킴).
    critical_open = 0
    vuln_rows = []  # (check_item, server, result) - 취약/수동확인 항목 전체
    for ci in items:
        for srv in servers:
            r = per_server[srv.id].get(ci.id)
            if r and r.result in ("취약", "수동확인"):
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
            if r.result in ("취약", "수동확인"):
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

    # --- 히트맵 (서버별 카드, 카테고리별로 뚜렷하게 나뉜 칩 목록) ----------------
    # 서버마다 카드 하나, 그 안에 카테고리 아코디언(server_detail과 동일 컴포넌트
    # 재사용)을 두고, 칩 안에 점검항목 코드를 직접 적어 옆에 라벨을 따로 안 둔다.
    def _cell_status(ci, srv):
        r = per_server[srv.id].get(ci.id)
        if r is None or r.result == "N/A":
            return dict(status="na", label="N/A")
        if r.result == "취약":
            return dict(status="vuln", label="취약")
        if r.result == "수동확인":
            return dict(status="manual", label="수동 조치 필요")
        return dict(status="good", label="양호")

    heatmap_categories = OrderedDict()
    for ci in items:
        heatmap_categories.setdefault(ci.category, []).append(ci)

    score_by_server = {s["server"].id: s for s in server_scores}
    heatmap_server_blocks = []
    for srv in servers:
        sc = score_by_server[srv.id]
        cat_blocks = []
        for cat, cis in heatmap_categories.items():
            cells = [dict(ci=ci, **_cell_status(ci, srv)) for ci in cis]
            stats = dict(vuln=0, manual=0, na=0, good=0)
            for cell in cells:
                stats[cell["status"]] += 1
            cat_blocks.append(dict(category=cat, cells=cells, stats=stats,
                                    open=bool(stats["vuln"] or stats["manual"])))
        heatmap_server_blocks.append(dict(server=srv, level=sc["level"], grade=sc["grade"],
                                           color=sc["color"], categories=cat_blocks))

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
        heatmap_servers=servers,
        heatmap_server_blocks=heatmap_server_blocks,
        RISK_LABEL=RISK_LABEL,
    )
