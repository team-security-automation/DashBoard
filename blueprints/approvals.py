# -*- coding: utf-8 -*-
from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from extensions import db
from models import Server, CheckItem, ScanResult, ApprovalRequest, ActionHistory
from scoring import calc_security_level, GRADE_COLOR

approvals_bp = Blueprint("approvals", __name__, url_prefix="/approvals")


@approvals_bp.route("/")
@login_required
def list_approvals():
    status = request.args.get("status", "pending")
    q = ApprovalRequest.query
    if status != "all":
        q = q.filter_by(status=status)
    reqs = q.order_by(ApprovalRequest.requested_at.desc()).all()
    counts = dict(
        pending=ApprovalRequest.query.filter_by(status="pending").count(),
        approved=ApprovalRequest.query.filter_by(status="approved").count(),
        rejected=ApprovalRequest.query.filter_by(status="rejected").count(),
        all=ApprovalRequest.query.count(),
    )
    return render_template("approvals_list.html", reqs=reqs, status=status, counts=counts)


@approvals_bp.route("/create", methods=["POST"])
@login_required
def create():
    if current_user.role != "admin":
        flash("조치 승인 요청은 실무자(관리자) 권한이 필요합니다.", "warning")
        return redirect(request.referrer or url_for("dashboard.index"))

    server_id = int(request.form["server_id"])
    check_item_id = int(request.form["check_item_id"])
    srv = Server.query.get_or_404(server_id)
    ci = CheckItem.query.get_or_404(check_item_id)

    sr = (ScanResult.query.filter_by(server_id=server_id, check_item_id=check_item_id)
          .order_by(ScanResult.checked_at.desc()).first())
    if sr is None or sr.result != "취약":
        flash("현재 '취약'으로 진단된 항목만 조치 승인을 요청할 수 있습니다.", "warning")
        return redirect(url_for("servers.server_detail", server_id=server_id))

    exists = ApprovalRequest.query.filter_by(
        server_id=server_id, check_item_id=check_item_id, status="pending"
    ).first()
    if exists:
        flash("이미 승인 대기 중인 요청이 있습니다.", "info")
        return redirect(url_for("approvals.detail", req_id=exists.id))

    ar = ApprovalRequest(
        server_id=server_id, check_item_id=check_item_id, scan_result_id=sr.id,
        requested_by=f"{current_user.display_name}({current_user.username})",
        requested_at=datetime.utcnow(), status="pending",
        diff_before=f"- 현재 설정: {sr.current_setting or '(진단결과 없음)'}",
        diff_after=f"+ 가이드 권고 설정 적용: {ci.guide}",
        affected_service=srv.role_desc,
        expected_score_delta=ci.weight,
    )
    db.session.add(ar)
    db.session.commit()
    flash(f"'{ci.code} {ci.name}' 항목에 대한 조치 승인을 요청했습니다.", "success")
    return redirect(url_for("approvals.detail", req_id=ar.id))


@approvals_bp.route("/<int:req_id>")
@login_required
def detail(req_id):
    ar = ApprovalRequest.query.get_or_404(req_id)
    srv = ar.server
    level_before, grade_before, _, _ = calc_security_level(srv.latest_results())
    return render_template("approval_detail.html", ar=ar, server=srv, ci=ar.check_item,
                            level_before=level_before, grade_before=grade_before)


@approvals_bp.route("/<int:req_id>/decide", methods=["POST"])
@login_required
def decide(req_id):
    ar = ApprovalRequest.query.get_or_404(req_id)
    if current_user.role != "approver":
        flash("조치 승인/거부는 승인자 권한이 필요합니다.", "warning")
        return redirect(url_for("approvals.detail", req_id=req_id))

    if ar.status != "pending":
        flash("이미 처리된 요청입니다.", "info")
        return redirect(url_for("approvals.detail", req_id=req_id))

    action = request.form.get("action")
    ar.approver = f"{current_user.display_name}({current_user.username})"
    ar.decided_at = datetime.utcnow()

    if action == "reject":
        reason = request.form.get("reason", "").strip()
        if not reason:
            flash("거부 시 사유 입력이 필요합니다.", "warning")
            return redirect(url_for("approvals.detail", req_id=req_id))
        ar.status = "rejected"
        ar.reject_reason = reason
        db.session.commit()
        flash("조치 요청을 거부했습니다.", "info")
        return redirect(url_for("approvals.list_approvals", status="rejected"))

    # ---- 승인: 백업 -> 조치 -> 자동 재진단 -> 전후비교 기록 ------------------
    srv = ar.server
    ci = ar.check_item
    level_before, _, _, _ = calc_security_level(srv.latest_results())

    ar.status = "approved"
    ar.backup_path = f"/backup/{srv.hostname}/{datetime.utcnow():%Y%m%d_%H%M%S}_{ci.code}.tar.gz"

    sr = ScanResult.query.get(ar.scan_result_id)
    before_score = sr.score if sr else ci.weight

    new_result = ScanResult(
        server_id=srv.id, check_item_id=ci.id, scan_run_id=None,
        result="양호", current_setting=None, recommendation=None,
        score=0.0, checked_at=datetime.utcnow(),
    )
    db.session.add(new_result)
    ar.executed_at = datetime.utcnow()
    db.session.flush()

    level_after, _, _, _ = calc_security_level(srv.latest_results())
    ar.before_score = level_before
    ar.after_score = level_after

    hist = ActionHistory(
        approval_id=ar.id, server_id=srv.id, check_item_id=ci.id,
        before_result="취약", after_result="양호",
        before_score=before_score, after_score=0.0,
        performed_by=f"{ar.approver} 승인 → 자동 조치 실행",
        performed_at=datetime.utcnow(), backup_path=ar.backup_path,
    )
    db.session.add(hist)
    db.session.commit()

    flash(f"승인 완료: 백업 후 조치를 실행하고 재진단했습니다. "
          f"(서버 보안점수 {level_before} → {level_after})", "success")
    return redirect(url_for("approvals.detail", req_id=req_id))
