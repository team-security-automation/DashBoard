# -*- coding: utf-8 -*-
import csv
import io
from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from extensions import db
from models import Server, CheckItem, ApprovalRequest, RISK_LABEL, OS_FAMILIES
from scoring import calc_security_level, calc_security_level_auto_only, GRADE_COLOR

servers_bp = Blueprint("servers", __name__, url_prefix="/servers")


def _require_admin():
    if current_user.role != "admin":
        flash("서버 관리는 실무자(관리자) 권한이 필요합니다.", "warning")
        return False
    return True


@servers_bp.route("/")
@login_required
def list_servers():
    q = request.args.get("q", "").strip()
    query = Server.query
    if q:
        query = query.filter(db.or_(Server.hostname.ilike(f"%{q}%"), Server.ip.ilike(f"%{q}%")))
    servers = query.order_by(Server.id).all()
    rows = []
    for srv in servers:
        level, grade, total, identified = calc_security_level(srv.latest_results())
        rows.append(dict(server=srv, level=level, grade=grade, color=GRADE_COLOR.get(grade, "warn")))
    return render_template("servers.html", rows=rows, q=q)


@servers_bp.route("/new", methods=["GET", "POST"])
@login_required
def new_server():
    if not _require_admin():
        return redirect(url_for("servers.list_servers"))

    if request.method == "POST":
        hostname = request.form["hostname"].strip()
        if Server.query.filter_by(hostname=hostname).first():
            flash(f"호스트명 '{hostname}'은(는) 이미 등록되어 있습니다. 다른 이름을 쓰세요.", "warning")
            return redirect(url_for("servers.new_server"))
        srv = Server(
            hostname=hostname,
            ip=request.form["ip"].strip(),
            os_family=request.form["os_family"].strip(),
            os_version=request.form["os_version"].strip(),
            role_desc=request.form.get("role_desc", "").strip(),
            business_name=request.form.get("business_name", "").strip(),
            business_team=request.form.get("business_team", "").strip(),
            owner=request.form.get("owner", "").strip(),
            asset_grade=request.form.get("asset_grade", "2등급"),
            is_web_db=bool(request.form.get("is_web_db")),
            ssh_user=request.form.get("ssh_user", "ansible").strip() or "ansible",
            ssh_port=int(request.form.get("ssh_port") or 22),
            ssh_key_path=request.form.get("ssh_key_path", "").strip() or None,
            ssh_become=bool(request.form.get("ssh_become")),
        )
        db.session.add(srv)
        db.session.commit()
        flash(f"서버 '{srv.hostname}'가 등록되었습니다. 진단 실행 화면에서 최초 진단을 실행하세요.", "success")
        return redirect(url_for("servers.list_servers"))

    return render_template("server_form.html", server=None, os_families=OS_FAMILIES)


@servers_bp.route("/upload-csv", methods=["POST"])
@login_required
def upload_csv():
    if not _require_admin():
        return redirect(url_for("servers.list_servers"))

    file = request.files.get("csv_file")
    if not file or file.filename == "":
        flash("CSV 파일을 선택해주세요. (형식: hostname,ip,os_family,os_version,role_desc,"
              "is_web_db,ssh_user,ssh_port,ssh_key_path,ssh_become)", "warning")
        return redirect(url_for("servers.list_servers"))

    # os_family는 자유 텍스트로 받으면 등록은 성공해놓고 진단 시 스크립트 폴더를
    # 못 찾아 조용히 실패한다 (개별 등록 폼은 라디오로 이미 막아뒀음). CSV도 똑같이
    # OS_FAMILIES 두 값만 허용하고, 대소문자/공백만 다른 정도는 정규화해서 받아준다.
    os_family_lookup = {f.strip().lower(): f for f in OS_FAMILIES}

    content = file.stream.read().decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))
    created = 0
    missing_ssh = []
    skipped = []
    # 아직 커밋 전이라 DB 조회만으로는 "같은 CSV 안에서 중복된 호스트명"을 못 잡는다
    # (기존 서버명이랑은 겹치는데 서로는 신경 안 쓰는 상태) - 이번 배치 안에서 이미
    # 쓴 이름도 같이 추적한다.
    existing_hostnames = {h.lower() for h, in db.session.query(Server.hostname).all()}
    for row in reader:
        if not row.get("hostname"):
            continue
        hostname = row["hostname"].strip()
        if hostname.lower() in existing_hostnames:
            skipped.append(f"{hostname} (호스트명 중복 - 이미 등록되어 있거나 이 CSV 안에서 중복됨)")
            continue
        raw_os_family = row.get("os_family", "").strip()
        os_family = os_family_lookup.get(raw_os_family.lower())
        if not os_family:
            skipped.append(f"{hostname} (os_family '{raw_os_family}' 인식 불가"
                            f" - {' 또는 '.join(OS_FAMILIES)}만 허용)")
            continue
        existing_hostnames.add(hostname.lower())
        ssh_key_path = row.get("ssh_key_path", "").strip() or None
        srv = Server(
            hostname=hostname,
            ip=row.get("ip", "").strip(),
            os_family=os_family,
            os_version=row.get("os_version", "").strip() or "-",
            role_desc=row.get("role_desc", "").strip(),
            business_name=row.get("business_name", "").strip(),
            owner=row.get("owner", "").strip(),
            is_web_db=(row.get("is_web_db", "").strip().lower() not in ("", "0", "false", "no")),
            # SSH 접속정보도 CSV로 같이 받아야 등록 즉시 진단 실행이 가능하다.
            # 안 채우면 개별 서버 수정 화면에서 나중에 채울 때까지 인벤토리에서 빠진다.
            ssh_user=row.get("ssh_user", "").strip() or "ansible",
            ssh_port=int(row["ssh_port"]) if row.get("ssh_port", "").strip() else 22,
            ssh_key_path=ssh_key_path,
            ssh_become=(row.get("ssh_become", "").strip().lower() not in ("", "0", "false", "no")),
        )
        db.session.add(srv)
        created += 1
        if not ssh_key_path:
            missing_ssh.append(srv.hostname)
    db.session.commit()
    msg = f"CSV 일괄 등록 완료: {created}건 등록되었습니다."
    if missing_ssh:
        msg += f" (SSH 키 경로 미입력 {len(missing_ssh)}건: {', '.join(missing_ssh)} - 진단 실행 전 서버 수정에서 채워야 함)"
    if skipped:
        msg += f" / 건너뜀 {len(skipped)}건: {'; '.join(skipped)}"
    flash(msg, "success" if not (missing_ssh or skipped) else "warning")
    return redirect(url_for("servers.list_servers"))


@servers_bp.route("/<int:server_id>/edit", methods=["GET", "POST"])
@login_required
def edit_server(server_id):
    srv = Server.query.get_or_404(server_id)
    if not _require_admin():
        return redirect(url_for("servers.list_servers"))

    if request.method == "POST":
        hostname = request.form["hostname"].strip()
        dup = Server.query.filter(Server.hostname == hostname, Server.id != server_id).first()
        if dup:
            flash(f"호스트명 '{hostname}'은(는) 이미 다른 서버(id={dup.id})에서 쓰고 있습니다.", "warning")
            return redirect(url_for("servers.edit_server", server_id=server_id))
        srv.hostname = hostname
        srv.ip = request.form["ip"].strip()
        srv.os_family = request.form["os_family"].strip()
        srv.os_version = request.form["os_version"].strip()
        srv.role_desc = request.form.get("role_desc", "").strip()
        srv.business_name = request.form.get("business_name", "").strip()
        srv.business_team = request.form.get("business_team", "").strip()
        srv.owner = request.form.get("owner", "").strip()
        srv.asset_grade = request.form.get("asset_grade", "2등급")
        srv.is_web_db = bool(request.form.get("is_web_db"))
        srv.ssh_user = request.form.get("ssh_user", "ansible").strip() or "ansible"
        srv.ssh_port = int(request.form.get("ssh_port") or 22)
        srv.ssh_key_path = request.form.get("ssh_key_path", "").strip() or None
        srv.ssh_become = bool(request.form.get("ssh_become"))
        db.session.commit()
        flash(f"서버 '{srv.hostname}' 정보가 수정되었습니다.", "success")
        return redirect(url_for("servers.list_servers"))

    return render_template("server_form.html", server=srv, os_families=OS_FAMILIES)


@servers_bp.route("/<int:server_id>/delete", methods=["POST"])
@login_required
def delete_server(server_id):
    srv = Server.query.get_or_404(server_id)
    if not _require_admin():
        return redirect(url_for("servers.list_servers"))
    name = srv.hostname
    db.session.delete(srv)
    db.session.commit()
    flash(f"서버 '{name}'가 삭제되었습니다.", "info")
    return redirect(url_for("servers.list_servers"))


@servers_bp.route("/<int:server_id>")
@login_required
def server_detail(server_id):
    srv = Server.query.get_or_404(server_id)
    results = srv.latest_results()
    level, grade, total, identified = calc_security_level(results)
    # "자동 진단 결과만 봤을 때"(수동확인 판정 전) 점수 - 수동확인을 취약처럼 감점하지
    # 않고 N/A처럼 분모에서 빼서 계산한다. 실무자가 수동확인을 판정할수록 이 값과
    # 위 level(수동확인 반영) 값이 서로 가까워지다가, 다 끝나면 둘이 같아진다.
    auto_level, auto_grade, _, _ = calc_security_level_auto_only(results)
    manual_pending = sum(1 for r in results if r.result == "수동확인")

    category = request.args.get("category", "")
    risk = request.args.get("risk", "")
    result_filter = request.args.get("result", "")
    q = request.args.get("q", "").strip()

    rows = []
    for r in results:
        ci = r.check_item
        if category and ci.category != category:
            continue
        if risk and ci.risk_level != risk:
            continue
        if result_filter and r.result != result_filter:
            continue
        if q and q.lower() not in ci.name.lower() and q.lower() not in ci.code.lower():
            continue
        rows.append(r)

    # 위험도순(상->중->하) 정렬 후 코드순
    risk_order = {"H": 0, "M": 1, "L": 2}
    rows.sort(key=lambda r: (risk_order.get(r.check_item.risk_level, 9), r.check_item.order_no))

    categories = sorted({r.check_item.category for r in results})

    # 카테고리별 아코디언 그룹 + 통계 (필터링된 rows 기준, 전체 카테고리 순서 유지)
    groups = []
    for cat in categories:
        cat_rows = [r for r in rows if r.check_item.category == cat]
        if not cat_rows:
            continue
        stats = {"vuln": 0, "manual": 0, "na": 0, "good": 0}
        for r in cat_rows:
            if r.result == "취약":
                stats["vuln"] += 1
            elif r.result == "수동확인":
                stats["manual"] += 1
            elif r.result == "N/A":
                stats["na"] += 1
            else:
                stats["good"] += 1
        needs_attention = stats["vuln"] > 0 or stats["manual"] > 0
        force_open = bool(q or category)
        groups.append(dict(category=cat, rows=cat_rows, stats=stats,
                            open=force_open or needs_attention))

    # 항목당 "가장 최근" 승인요청 하나만 상태 표시에 쓴다 (여러 번 요청->거부->재요청
    # 됐을 수 있어 최신 것 기준으로 판단). 승인상태를 진단결과 표 안에 그대로 보여줘서
    # 이 항목이 지금 조치 승인 프로세스의 어느 단계인지 다른 화면(조치승인 목록) 안
    # 들어가도 바로 보이게 한다.
    all_reqs = (ApprovalRequest.query
                .filter_by(server_id=server_id)
                .order_by(ApprovalRequest.requested_at.desc()).all())
    approval_map = {}
    for a in all_reqs:
        approval_map.setdefault(a.check_item_id, a)

    # "지금 뭘 처리해야 하는지" 한눈에 보는 요약. "승인"과 "조치"는 서로 다른 사람이
    # 하는 서로 다른 일(승인자가 허용해야만 실무자가 조치할 수 있음)이라 화면도
    # 완전히 분리한다. 딱 3종류:
    #   1) 수동확인 항목 - 스크립트가 양호/취약을 못 정한 것 (판정 자체가 할 일)
    #   2) 승인 요청 - "아직 승인이 안 끝난" 전부: 요청 전(신규) + 대기중 + 거부됨
    #      (재요청 가능). 승인자의 결정을 기다리는 단계라 조치 화면엔 안 보인다.
    #   3) 조치하기 - 승인이 끝난(approved) 것만. 자동조치는 승인 전엔 이 화면에
    #      아예 나타나지 않고, 승인된 것만 체크박스로 골라 실행할 수 있다 - "승인
    #      받아야 조치 버튼이 활성화된다"는 걸 화면 분리 자체로 보여준다.
    #      완전히 끝난 것(승인+실행완료)만 여기서 빠진다.
    summary = {"수동확인 항목": [], "승인 요청": [], "조치하기": []}
    # 수동확인 일괄판정 드로어는 check_item_id가 아니라 review.bulk_decide가 받는
    # scan_result_id가 필요해서, 그 항목만 (ScanResult, CheckItem) 쌍으로 따로 챙긴다.
    manual_pending_pairs = []
    # 드로어 안에서 자동/수동 조치를 각각 다른 액션(자동=일괄 가능, 수동=조치 계획
    # 텍스트가 매번 달라서 항목별 개별 처리)으로 보여줘야 해서 Jinja 안에서 필터링하는
    # 대신 파이썬에서 미리 나눠둔다 (더 명확하고 안전함).
    drawer_data = {
        "auto": {"to_request": [], "pending": [], "rejected": [], "ready": []},
        "manual": {"to_request": [], "pending": [], "rejected": [], "ready": []},
    }
    for r in results:
        ci = r.check_item
        ar = approval_map.get(ci.id)
        if r.result == "수동확인" and (ar is None or ar.status == "rejected"):
            summary["수동확인 항목"].append(ci)
            manual_pending_pairs.append(r)
        elif r.result == "취약":
            already_done = ar is not None and ar.status == "approved" and ar.executed_at is not None
            if already_done:
                continue
            kind = "auto" if r.remediation_type == "auto" else "manual"
            if ar is None:
                summary["승인 요청"].append(ci)
                drawer_data[kind]["to_request"].append(ci)
            elif ar.status == "pending":
                summary["승인 요청"].append(ci)
                drawer_data[kind]["pending"].append(ci)
            elif ar.status == "rejected":
                summary["승인 요청"].append(ci)
                drawer_data[kind]["rejected"].append((ci, ar))
            elif ar.status == "approved":
                summary["조치하기"].append(ci)
                drawer_data[kind]["ready"].append((ci, ar))

    # 드로어 안에서 카테고리별로 묶어 보여줄 거라 미리 카테고리순으로 정렬해둔다
    # (Jinja groupby는 연속된 값끼리만 묶어서, 정렬 안 하면 카테고리가 흩어져 보인다).
    for lst in summary.values():
        lst.sort(key=lambda ci: (ci.category, ci.order_no))
    manual_pending_pairs.sort(key=lambda r: (r.check_item.category, r.check_item.order_no))
    for kind_data in drawer_data.values():
        kind_data["to_request"].sort(key=lambda ci: (ci.category, ci.order_no))
        kind_data["pending"].sort(key=lambda ci: (ci.category, ci.order_no))
        kind_data["rejected"].sort(key=lambda pair: (pair[0].category, pair[0].order_no))
        kind_data["ready"].sort(key=lambda pair: (pair[0].category, pair[0].order_no))

    return render_template(
        "server_detail.html",
        server=srv, level=level, grade=grade, color=GRADE_COLOR.get(grade, "warn"),
        auto_level=auto_level, auto_grade=auto_grade, auto_color=GRADE_COLOR.get(auto_grade, "warn"),
        manual_pending=manual_pending,
        rows=rows, categories=categories, groups=groups,
        f_category=category, f_risk=risk, f_result=result_filter, f_q=q,
        RISK_LABEL=RISK_LABEL, approval_map=approval_map, summary=summary,
        manual_pending_pairs=manual_pending_pairs, drawer_data=drawer_data,
    )
