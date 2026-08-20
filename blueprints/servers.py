# -*- coding: utf-8 -*-
import csv
import io
from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from extensions import db
from models import Server, CheckItem, ApprovalRequest, RISK_LABEL, OS_FAMILIES
from scoring import calc_security_level, GRADE_COLOR

servers_bp = Blueprint("servers", __name__, url_prefix="/servers")


def _require_admin():
    if current_user.role != "admin":
        flash("서버 관리는 실무자(관리자) 권한이 필요합니다.", "warning")
        return False
    return True


@servers_bp.route("/")
@login_required
def list_servers():
    servers = Server.query.order_by(Server.id).all()
    rows = []
    for srv in servers:
        level, grade, total, identified = calc_security_level(srv.latest_results())
        rows.append(dict(server=srv, level=level, grade=grade, color=GRADE_COLOR.get(grade, "warn")))
    return render_template("servers.html", rows=rows)


@servers_bp.route("/new", methods=["GET", "POST"])
@login_required
def new_server():
    if not _require_admin():
        return redirect(url_for("servers.list_servers"))

    if request.method == "POST":
        srv = Server(
            hostname=request.form["hostname"].strip(),
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
    for row in reader:
        if not row.get("hostname"):
            continue
        raw_os_family = row.get("os_family", "").strip()
        os_family = os_family_lookup.get(raw_os_family.lower())
        if not os_family:
            skipped.append(f"{row['hostname'].strip()} (os_family '{raw_os_family}' 인식 불가"
                            f" - {' 또는 '.join(OS_FAMILIES)}만 허용)")
            continue
        ssh_key_path = row.get("ssh_key_path", "").strip() or None
        srv = Server(
            hostname=row["hostname"].strip(),
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
        srv.hostname = request.form["hostname"].strip()
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

    pending = (ApprovalRequest.query
               .filter_by(server_id=server_id, status="pending").all())
    pending_map = {p.check_item_id: p.id for p in pending}

    return render_template(
        "server_detail.html",
        server=srv, level=level, grade=grade, color=GRADE_COLOR.get(grade, "warn"),
        rows=rows, categories=categories, groups=groups,
        f_category=category, f_risk=risk, f_result=result_filter, f_q=q,
        RISK_LABEL=RISK_LABEL, pending_map=pending_map,
    )
