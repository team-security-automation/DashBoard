# -*- coding: utf-8 -*-
from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from extensions import db
from models import Server, CheckItem, ScanResult, ApprovalRequest, ActionHistory
from scoring import calc_security_level, GRADE_COLOR
from impact import get_impact

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


@approvals_bp.route("/bulk-create", methods=["POST"])
@login_required
def bulk_create():
    """체크박스로 고른 취약/수동확인 항목 여러 건에 대해 한 번에 승인 요청을 보낸다.
    항목은 "server_id:check_item_id" 쌍의 목록으로 받는다 (서버 하나로 제한하지
    않음 - 서버 상세 페이지의 "지금 처리할 것" 패널(한 서버)뿐 아니라, 나중에
    여러 서버에 걸친 화면에서도 같은 엔드포인트를 재사용할 수 있게). create()와
    항목당 규칙은 동일 - 대상이 아니거나 이미 대기 중인 건 건너뛴다."""
    next_url = request.form.get("next")
    if current_user.role != "admin":
        flash("조치 승인 요청은 실무자(관리자) 권한이 필요합니다.", "warning")
        return redirect(next_url or url_for("dashboard.index"))

    pairs = []
    for raw in request.form.getlist("items"):
        try:
            sid_str, cid_str = raw.split(":")
            pairs.append((int(sid_str), int(cid_str)))
        except ValueError:
            continue
    if not pairs:
        flash("선택된 항목이 없습니다.", "warning")
        return redirect(next_url or url_for("dashboard.index"))

    requested_by = f"{current_user.display_name}({current_user.username})"
    server_cache = {}
    done, skipped = 0, 0
    for server_id, check_item_id in pairs:
        srv = server_cache.get(server_id) or Server.query.get(server_id)
        server_cache[server_id] = srv
        ci = CheckItem.query.get(check_item_id)
        sr = (ScanResult.query.filter_by(server_id=server_id, check_item_id=check_item_id)
              .order_by(ScanResult.checked_at.desc()).first() if srv else None)
        if not srv or not ci or sr is None or sr.result not in ("취약", "수동확인"):
            skipped += 1
            continue
        exists = ApprovalRequest.query.filter_by(
            server_id=server_id, check_item_id=check_item_id, status="pending"
        ).first()
        if exists:
            skipped += 1
            continue
        remediation_type = "manual" if sr.result == "수동확인" else (sr.remediation_type or "auto")
        db.session.add(ApprovalRequest(
            server_id=server_id, check_item_id=check_item_id, scan_result_id=sr.id,
            requested_by=requested_by, requested_at=datetime.utcnow(), status="pending",
            diff_before=f"- 현재 설정: {sr.current_setting or '(진단결과 없음)'}",
            diff_after=f"+ 가이드 권고 설정 적용: {ci.guide}",
            affected_service=srv.role_desc, expected_score_delta=ci.weight,
            remediation_type=remediation_type,
        ))
        done += 1
    db.session.commit()

    msg = f"{done}건 조치 승인을 일괄 요청했습니다."
    if skipped:
        msg += f" (대상이 아니거나 이미 대기 중인 {skipped}건은 건너뜀)"
    flash(msg, "success")
    return redirect(next_url or url_for("dashboard.index"))


@approvals_bp.route("/create", methods=["POST"])
@login_required
def create():
    next_url = request.form.get("next")
    if current_user.role != "admin":
        flash("조치 승인 요청은 실무자(관리자) 권한이 필요합니다.", "warning")
        return redirect(next_url or request.referrer or url_for("dashboard.index"))

    server_id = int(request.form["server_id"])
    check_item_id = int(request.form["check_item_id"])
    srv = Server.query.get_or_404(server_id)
    ci = CheckItem.query.get_or_404(check_item_id)

    sr = (ScanResult.query.filter_by(server_id=server_id, check_item_id=check_item_id)
          .order_by(ScanResult.checked_at.desc()).first())
    if sr is None or sr.result not in ("취약", "수동확인"):
        flash("현재 '취약' 또는 '수동확인'으로 진단된 항목만 조치 승인을 요청할 수 있습니다.", "warning")
        return redirect(next_url or url_for("servers.server_detail", server_id=server_id))

    exists = ApprovalRequest.query.filter_by(
        server_id=server_id, check_item_id=check_item_id, status="pending"
    ).first()
    if exists:
        flash("이미 승인 대기 중인 요청이 있습니다.", "info")
        return redirect(next_url or url_for("servers.server_detail", server_id=server_id))

    # 수동확인 항목은 그 자체가 "자동으로 양호/취약을 판정 못해 사람이 봐야 하는" 상태라
    # 자동 조치 대상이 될 수 없다 - 항상 수동 조치(승인 -> 실무자 완료 처리) 경로를 탄다.
    remediation_type = "manual" if sr.result == "수동확인" else (sr.remediation_type or "auto")

    # 수동 조치는 대시보드가 대신 실행할 수 없어서, 실무자가 "무엇을 어떻게 할지" 계획을
    # 직접 적어 승인자에게 보여줘야 한다 - 자동 조치는 가이드 문구를 그대로 쓴다.
    plan_note = request.form.get("plan_note", "").strip()
    if remediation_type == "manual" and plan_note:
        diff_after = f"+ {plan_note}"
    else:
        diff_after = f"+ 가이드 권고 설정 적용: {ci.guide}"

    ar = ApprovalRequest(
        server_id=server_id, check_item_id=check_item_id, scan_result_id=sr.id,
        requested_by=f"{current_user.display_name}({current_user.username})",
        requested_at=datetime.utcnow(), status="pending",
        diff_before=f"- 현재 설정: {sr.current_setting or '(진단결과 없음)'}",
        diff_after=diff_after,
        affected_service=srv.role_desc,
        expected_score_delta=ci.weight,
        remediation_type=remediation_type,
    )
    db.session.add(ar)
    db.session.commit()
    flash(f"'{ci.code} {ci.name}' 항목에 대한 조치 승인을 요청했습니다.", "success")
    return redirect(next_url or url_for("servers.server_detail", server_id=server_id))


@approvals_bp.route("/<int:req_id>")
@login_required
def detail(req_id):
    ar = ApprovalRequest.query.get_or_404(req_id)
    srv = ar.server
    level_before, grade_before, _, _ = calc_security_level(srv.latest_results())
    impact = get_impact(ar.check_item.code)
    sr = ScanResult.query.get(ar.scan_result_id)
    before_result = sr.result if sr else "취약"
    return render_template("approval_detail.html", ar=ar, server=srv, ci=ar.check_item,
                            level_before=level_before, grade_before=grade_before, impact=impact,
                            before_result=before_result)


def _complete_manual_remediation(ar, performed_by_suffix, work_note=None):
    """수동 조치 완료 처리 전용. 실무자가 직접 서버에 들어가 고친 뒤 "이렇게 했다"고
    남기는 절차라, 시스템이 SSH로 뭘 실행하는 게 아니라 그 증언을 그대로 기록만 한다."""
    srv = ar.server
    ci = ar.check_item
    level_before, _, _, _ = calc_security_level(srv.latest_results())

    ar.backup_path = f"/backup/{srv.hostname}/{datetime.utcnow():%Y%m%d_%H%M%S}_{ci.code}.tar.gz"

    sr = ScanResult.query.get(ar.scan_result_id)
    before_score = sr.score if sr else ci.weight
    before_result = sr.result if sr else "취약"

    new_result = ScanResult(
        server_id=srv.id, check_item_id=ci.id, scan_run_id=None,
        result="양호", current_setting=None, recommendation=None,
        score=0.0, remediation_type=ar.remediation_type, checked_at=datetime.utcnow(),
    )
    db.session.add(new_result)
    ar.executed_at = datetime.utcnow()
    db.session.flush()

    level_after, _, _, _ = calc_security_level(srv.latest_results())
    ar.before_score = level_before
    ar.after_score = level_after
    ar.work_note = work_note

    hist = ActionHistory(
        approval_id=ar.id, server_id=srv.id, check_item_id=ci.id,
        before_result=before_result, after_result="양호",
        before_score=before_score, after_score=0.0,
        performed_by=f"{ar.approver} 승인 · {performed_by_suffix}",
        performed_at=datetime.utcnow(), backup_path=ar.backup_path,
        work_note=work_note,
    )
    db.session.add(hist)
    db.session.commit()
    return level_before, level_after


def _execute_remediation_auto(ar, performed_by_suffix):
    """자동 조치 실제 실행. playbooks/fix.yaml로 실제 SSH 접속 -> 해당 서버에서
    check_item의 *_fix.sh 실행 -> 결과 JSON을 받아와 그대로 반영한다 (DB 시뮬레이션 아님).
    반환값: (level_before, level_after, 실패 시 사람이 읽을 사유 또는 None)
    조치가 실패하면(ansible 실행 자체 실패 / 스크립트가 실패·재확인 여전히 취약 보고)
    executed_at을 건드리지 않아 "자동 조치 실행" 버튼이 남아있어 재시도할 수 있다."""
    from blueprints.diagnosis import run_fix_real, fix_item_outcome, fix_item_code

    srv = ar.server
    ci = ar.check_item
    level_before, _, _, _ = calc_security_level(srv.latest_results())

    sr = ScanResult.query.get(ar.scan_result_id)
    before_score = sr.score if sr else ci.weight
    before_result = sr.result if sr else "취약"

    ok, items, err = run_fix_real(srv, [ci.code])
    item = next((x for x in items if fix_item_code(x) == ci.code), None) if ok else None

    if not ok or item is None:
        fail_reason = err or f"조치 결과에서 {ci.code} 항목을 찾지 못했습니다."
        db.session.add(ActionHistory(
            approval_id=ar.id, server_id=srv.id, check_item_id=ci.id,
            before_result=before_result, after_result=before_result,
            before_score=before_score, after_score=before_score,
            performed_by=f"{ar.approver} 승인 · {performed_by_suffix}",
            performed_at=datetime.utcnow(),
            work_note=f"[조치 실행 실패] {fail_reason}",
        ))
        db.session.commit()
        return None, None, fail_reason

    fix_ok, result, backup_path, detail = fix_item_outcome(item)
    new_score = 0.0 if result == "양호" else ci.weight

    db.session.add(ScanResult(
        server_id=srv.id, check_item_id=ci.id, scan_run_id=None,
        result=result, current_setting=None, recommendation=None,
        score=new_score, remediation_type=ar.remediation_type, checked_at=datetime.utcnow(),
    ))
    if backup_path:
        ar.backup_path = backup_path
    if fix_ok:
        ar.executed_at = datetime.utcnow()
    db.session.flush()

    level_after, _, _, _ = calc_security_level(srv.latest_results())
    ar.before_score = level_before
    ar.after_score = level_after

    db.session.add(ActionHistory(
        approval_id=ar.id, server_id=srv.id, check_item_id=ci.id,
        before_result=before_result, after_result=result,
        before_score=before_score, after_score=new_score,
        performed_by=f"{ar.approver} 승인 · {performed_by_suffix}",
        performed_at=datetime.utcnow(), backup_path=backup_path,
        work_note=detail,
    ))
    db.session.commit()
    return level_before, level_after, (None if fix_ok else (detail or "재확인 결과 여전히 취약"))


@approvals_bp.route("/<int:req_id>/decide", methods=["POST"])
@login_required
def decide(req_id):
    ar = ApprovalRequest.query.get_or_404(req_id)
    # 서버 상세 페이지에서 눌렀으면 그 페이지로, 승인 목록에서 눌렀으면 승인 목록으로
    # 돌아간다 (next 히든필드로 넘어옴 - 없으면 기존처럼 승인 상세로).
    next_url = request.form.get("next")
    if current_user.role != "approver":
        flash("조치 승인/거부는 승인자 권한이 필요합니다.", "warning")
        return redirect(next_url or url_for("approvals.detail", req_id=req_id))

    if ar.status != "pending":
        flash("이미 처리된 요청입니다.", "info")
        return redirect(next_url or url_for("approvals.detail", req_id=req_id))

    action = request.form.get("action")
    ar.approver = f"{current_user.display_name}({current_user.username})"
    ar.decided_at = datetime.utcnow()

    if action == "reject":
        reason = request.form.get("reason", "").strip()
        if not reason:
            flash("거부 시 사유 입력이 필요합니다.", "warning")
            return redirect(next_url or url_for("approvals.detail", req_id=req_id))
        ar.status = "rejected"
        ar.reject_reason = reason
        db.session.commit()
        flash("조치 요청을 거부했습니다.", "info")
        return redirect(next_url or url_for("approvals.list_approvals", status="rejected"))

    # ---- 승인 -----------------------------------------------------------
    # 승인자의 "승인"은 허가일 뿐, 조치 실행과는 분리한다. remediation_type과
    # 무관하게 여기서는 상태만 "approved"로 바꾸고 끝낸다.
    #   remediation_type == "auto"  : 실무자가 "자동 조치 실행" 버튼을 눌러야
    #                                  execute()가 백업 -> 조치 -> 재진단을 수행한다.
    #   remediation_type == "manual": 실무자가 직접 조치한 뒤 "수동 조치 완료 처리"를
    #                                  눌러야 ScanResult가 갱신된다 (complete_manual 참고).
    ar.status = "approved"
    ar.approve_note = request.form.get("note", "").strip() or None
    db.session.commit()

    if ar.remediation_type == "manual":
        flash("승인 완료: 이 항목은 수동 조치 대상입니다. 실무자가 직접 조치한 뒤 "
              "'수동 조치 완료 처리' 버튼을 눌러야 재진단·점수 반영이 됩니다.", "warning")
    else:
        flash("승인 완료: 조치 실행 대기 상태입니다. 실무자가 '자동 조치 실행' 버튼을 눌러야 "
              "백업·설정 변경·재진단이 진행됩니다.", "warning")
    return redirect(next_url or url_for("approvals.detail", req_id=req_id))


@approvals_bp.route("/<int:req_id>/execute", methods=["POST"])
@login_required
def execute(req_id):
    """승인된 자동조치 항목을 실무자가 직접 실행한다 (승인과 실행을 분리)."""
    ar = ApprovalRequest.query.get_or_404(req_id)
    next_url = request.form.get("next")
    if current_user.role != "admin":
        flash("자동 조치 실행은 실무자(관리자) 권한이 필요합니다.", "warning")
        return redirect(next_url or url_for("approvals.detail", req_id=req_id))

    if ar.status != "approved" or ar.remediation_type != "auto":
        flash("자동 조치 실행 대상이 아닙니다.", "info")
        return redirect(next_url or url_for("approvals.detail", req_id=req_id))

    if ar.executed_at is not None:
        flash("이미 실행된 요청입니다.", "info")
        return redirect(next_url or url_for("approvals.detail", req_id=req_id))

    level_before, level_after, fail_reason = _execute_remediation_auto(
        ar, f"{current_user.display_name}({current_user.username}) 자동 조치 실행"
    )
    if fail_reason:
        flash(f"자동 조치 실행에 실패했습니다: {fail_reason}", "danger")
    else:
        flash(f"자동 조치를 실행했습니다. 서버 보안점수가 {level_before}점에서 {level_after}점으로 올랐습니다.", "success")
    return redirect(next_url or url_for("approvals.detail", req_id=req_id))


@approvals_bp.route("/bulk-decide", methods=["POST"])
@login_required
def bulk_decide():
    """승인자가 여러 건을 체크박스로 골라 한 번에 승인/거부한다. decide()와 규칙은
    동일 - status가 pending이 아닌 건(이미 처리됨)은 건너뛰고 개수로 알려준다."""
    if current_user.role != "approver":
        flash("조치 승인/거부는 승인자 권한이 필요합니다.", "warning")
        return redirect(url_for("approvals.list_approvals", status="pending"))

    ids = request.form.getlist("req_ids", type=int)
    action = request.form.get("action")
    if not ids:
        flash("선택된 항목이 없습니다.", "warning")
        return redirect(url_for("approvals.list_approvals", status="pending"))

    reason = request.form.get("reason", "").strip()
    if action == "reject" and not reason:
        flash("거부 시 사유 입력이 필요합니다.", "warning")
        return redirect(url_for("approvals.list_approvals", status="pending"))

    done, skipped = 0, 0
    approver_label = f"{current_user.display_name}({current_user.username})"
    for req_id in ids:
        ar = ApprovalRequest.query.get(req_id)
        if not ar or ar.status != "pending":
            skipped += 1
            continue
        ar.approver = approver_label
        ar.decided_at = datetime.utcnow()
        if action == "reject":
            ar.status = "rejected"
            ar.reject_reason = reason
        else:
            ar.status = "approved"
            ar.approve_note = request.form.get("note", "").strip() or None
        done += 1
    db.session.commit()

    label = "거부" if action == "reject" else "승인 (자동 조치 대상은 실무자의 실행 대기 상태)"
    msg = f"{done}건 일괄 {label} 완료."
    if skipped:
        msg += f" 이미 처리되어 건너뛴 항목 {skipped}건."
    flash(msg, "success")
    return redirect(url_for("approvals.list_approvals", status="rejected" if action == "reject" else "pending"))


@approvals_bp.route("/bulk-execute", methods=["POST"])
@login_required
def bulk_execute():
    """실무자가 승인된 자동조치 항목 여러 건을 체크박스로 골라 한 번에 실행한다.
    execute()와 대상 규칙 동일(approved+auto+미실행) - 대상이 아닌 건 건너뛴다."""
    if current_user.role != "admin":
        flash("자동 조치 실행은 실무자(관리자) 권한이 필요합니다.", "warning")
        return redirect(url_for("approvals.list_approvals", status="approved"))

    ids = request.form.getlist("req_ids", type=int)
    if not ids:
        flash("선택된 항목이 없습니다.", "warning")
        return redirect(url_for("approvals.list_approvals", status="approved"))

    performed_by = f"{current_user.display_name}({current_user.username}) 자동 조치 실행(일괄)"
    done, failed, skipped = 0, 0, 0
    for req_id in ids:
        ar = ApprovalRequest.query.get(req_id)
        if not ar or ar.status != "approved" or ar.remediation_type != "auto" or ar.executed_at is not None:
            skipped += 1
            continue
        _, _, fail_reason = _execute_remediation_auto(ar, performed_by)
        if fail_reason:
            failed += 1
        else:
            done += 1

    msg = f"{done}건 자동 조치를 실행했습니다."
    if failed:
        msg += f" {failed}건은 실행에 실패했습니다(각 항목 상세에서 사유 확인)."
    if skipped:
        msg += f" 대상이 아니거나 이미 실행된 항목 {skipped}건은 건너뛰었습니다."
    flash(msg, "danger" if failed and not done else "success")
    return redirect(url_for("approvals.list_approvals", status="approved"))


@approvals_bp.route("/<int:req_id>/complete-manual", methods=["POST"])
@login_required
def complete_manual(req_id):
    ar = ApprovalRequest.query.get_or_404(req_id)
    next_url = request.form.get("next")
    if current_user.role != "admin":
        flash("수동 조치 완료 처리는 실무자(관리자) 권한이 필요합니다.", "warning")
        return redirect(next_url or url_for("approvals.detail", req_id=req_id))

    if ar.status != "approved" or ar.remediation_type != "manual":
        flash("수동 조치 완료 처리 대상이 아닙니다.", "info")
        return redirect(next_url or url_for("approvals.detail", req_id=req_id))

    if ar.executed_at is not None:
        flash("이미 완료 처리된 요청입니다.", "info")
        return redirect(next_url or url_for("approvals.detail", req_id=req_id))

    work_note = request.form.get("work_note", "").strip()
    if not work_note:
        flash("수동 조치 완료 처리는 실제로 무엇을/어떻게 조치했는지 조치 내용을 남겨야 합니다.", "warning")
        return redirect(next_url or url_for("approvals.detail", req_id=req_id))

    level_before, level_after = _complete_manual_remediation(
        ar, f"{current_user.display_name}({current_user.username}) 수동 조치 완료 처리",
        work_note=work_note,
    )
    flash(f"수동 조치 완료 처리했습니다. 서버 보안점수가 {level_before}점에서 {level_after}점으로 올랐습니다.", "success")
    return redirect(next_url or url_for("approvals.detail", req_id=req_id))
