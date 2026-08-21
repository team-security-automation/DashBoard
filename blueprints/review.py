# -*- coding: utf-8 -*-
"""
수동확인 판정
--------------
스크립트가 자동으로 양호/취약을 판정하지 못해 "수동확인" 상태로 남은 항목을,
실무자가 현재 설정값과 판정 근거(evidence)를 보고 그 자리에서 양호/취약으로
확정하는 화면. 조치 승인 절차(approvals)와 달리 백업·재진단이 필요한 원격
조치가 아니라 "판정" 그 자체이므로, 확정 즉시 진단 결과에 반영한다.
"""
from collections import OrderedDict

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user

from extensions import db
from models import Server, ScanResult, RISK_LABEL
from scoring import calc_security_level, grade_of, item_score_value, GRADE_COLOR

review_bp = Blueprint("review", __name__, url_prefix="/review")

_RISK_ORDER = {"H": 0, "M": 1, "L": 2}


def pending_manual_rows():
    """서버별 최신 진단 결과 중 result == '수동확인'인 항목을 (server, ScanResult) 쌍으로 모은다."""
    rows = []
    for srv in Server.query.order_by(Server.id).all():
        for r in srv.latest_results():
            if r.result == "수동확인":
                rows.append((srv, r))
    return rows


def pending_manual_count():
    return len(pending_manual_rows())


def _group_by_server(rows):
    by_server = OrderedDict()
    for srv, r in rows:
        by_server.setdefault(srv, []).append(r)
    return by_server


def _server_summaries(by_server):
    """서버 목록 화면에 쓸 요약 - 서버당 미확인 건수와 그 중 가장 급한 위험도."""
    summaries = []
    for srv, rs in by_server.items():
        top_risk = min((r.check_item.risk_level for r in rs), key=lambda x: _RISK_ORDER.get(x, 9))
        summaries.append(dict(server=srv, count=len(rs), top_risk=top_risk))
    summaries.sort(key=lambda s: (-s["count"], _RISK_ORDER.get(s["top_risk"], 9)))
    return summaries


def _overall_avg_score():
    servers = Server.query.all()
    if not servers:
        return 0.0, "-"
    total = sum(calc_security_level(srv.latest_results())[0] for srv in servers)
    avg = round(total / len(servers), 1)
    return avg, grade_of(avg)


@review_bp.route("/")
@login_required
def index():
    rows = pending_manual_rows()
    by_server = _group_by_server(rows)

    server_id = request.args.get("server_id", type=int)
    selected_server = db.session.get(Server, server_id) if server_id else None

    cards = []
    if selected_server:
        cards = [
            dict(scan_result_id=r.id, server=selected_server, ci=r.check_item,
                 current_setting=r.current_setting, evidence=r.evidence)
            for r in by_server.get(selected_server, [])
        ]

    avg_score, avg_grade = _overall_avg_score()
    return render_template(
        "review.html",
        server_summaries=_server_summaries(by_server),
        selected_server=selected_server,
        cards=cards,
        pending_count=len(rows),
        avg_score=avg_score,
        avg_grade=avg_grade,
        avg_color=GRADE_COLOR.get(avg_grade, "warn"),
        RISK_LABEL=RISK_LABEL,
    )


@review_bp.route("/bulk-decide", methods=["POST"])
@login_required
def bulk_decide():
    """서버 상세 페이지의 "지금 처리할 것" 패널에서 수동확인 여러 건을 한 번에
    양호/취약으로 판정한다. 한 건씩 처리하는 decide()(JSON, 즉시반영)와 달리
    폼 POST로 받아서 처리 후 원래 페이지로 되돌아간다."""
    next_url = request.form.get("next")
    if not current_user.can_run_diagnosis():
        flash("수동확인 판정은 실무자(관리자) 권한이 필요합니다.", "warning")
        return redirect(next_url or url_for("review.index"))

    ids = request.form.getlist("scan_result_ids", type=int)
    outcome = request.form.get("result")
    if not ids:
        flash("선택된 항목이 없습니다.", "warning")
        return redirect(next_url or url_for("review.index"))
    if outcome not in ("양호", "취약"):
        flash("잘못된 판정값입니다.", "warning")
        return redirect(next_url or url_for("review.index"))

    done = 0
    for sr_id in ids:
        sr = db.session.get(ScanResult, sr_id)
        if sr is None or sr.result != "수동확인":
            continue
        sr.result = outcome
        sr.score = item_score_value(sr.check_item.risk_level, outcome)
        done += 1
    db.session.commit()
    flash(f"{done}건을 '{outcome}'(으)로 일괄 판정했습니다.", "success")
    return redirect(next_url or url_for("review.index"))


@review_bp.route("/<int:scan_result_id>/decide", methods=["POST"])
@login_required
def decide(scan_result_id):
    if not current_user.can_run_diagnosis():
        return jsonify(ok=False, error="실무자(관리자) 권한이 필요합니다."), 403

    sr = db.session.get(ScanResult, scan_result_id)
    if sr is None or sr.result != "수동확인":
        return jsonify(ok=False, error="이미 처리되었거나 존재하지 않는 항목입니다."), 404

    outcome = (request.get_json(silent=True) or {}).get("result")
    if outcome not in ("양호", "취약"):
        return jsonify(ok=False, error="잘못된 판정값입니다."), 400

    server = sr.server
    level_before, _, _, _ = calc_security_level(server.latest_results())

    sr.result = outcome
    sr.score = item_score_value(sr.check_item.risk_level, outcome)
    db.session.commit()

    # 서버 상세 페이지(server_detail.html)에서 이 항목 하나를 판정했을 때 "이 서버"
    # 점수가 얼마나 바뀌었는지 바로 보여주려면 전체 평균이 아니라 이 서버 기준 점수가
    # 필요하다 (평균은 여러 서버에 묻혀서 체감이 안 됨 - /review 페이지는 계속 평균 사용).
    level_after, grade_after, _, _ = calc_security_level(server.latest_results())

    avg_score, avg_grade = _overall_avg_score()
    return jsonify(
        ok=True,
        pending_count=pending_manual_count(),
        avg_score=avg_score,
        avg_grade=avg_grade,
        avg_color=GRADE_COLOR.get(avg_grade, "warn"),
        server_id=server.id,
        server_level_before=level_before,
        server_level_after=level_after,
        server_grade_after=grade_after,
        server_color_after=GRADE_COLOR.get(grade_after, "warn"),
    )
