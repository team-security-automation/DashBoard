# -*- coding: utf-8 -*-
import json
import threading
import time
from datetime import datetime
from pathlib import Path

from flask import Blueprint, render_template, request, redirect, url_for, jsonify, current_app, flash
from flask_login import login_required, current_user

from extensions import db
from models import Server, ScanRun, ScanResult, CheckItem
from inventory import generate_inventory, servers_missing_ssh_config, ANSIBLE_DIR

diagnosis_bp = Blueprint("diagnosis", __name__, url_prefix="/diagnosis")

SCAN_RESULTS_DIR = Path(ANSIBLE_DIR).parent / "scan_results"
PLAYBOOK_RELATIVE_PATH = "playbooks/diagnose.yml"


def _require_admin():
    if current_user.role != "admin":
        flash("진단 실행은 실무자(관리자) 권한이 필요합니다.", "warning")
        return False
    return True


# ---------------------------------------------------------------------------
# 시뮬레이션 모드 (USE_REAL_ANSIBLE=False, 기본값)
# Ansible 미설치 상태에서도 대시보드 UI/워크플로를 그대로 테스트할 수 있게
# 남겨둔다. 직전 최신 결과를 새 타임스탬프로 재적재만 한다 - 실제 SSH 없음.
# ---------------------------------------------------------------------------
def _run_scan_simulated(app, run_id, server_ids, seconds_per_server):
    with app.app_context():
        run = db.session.get(ScanRun, run_id)
        for sid in server_ids:
            time.sleep(seconds_per_server)
            srv = db.session.get(Server, sid)
            if srv is None:
                continue
            latest = srv.latest_results()
            now = datetime.utcnow()
            new_rows = [
                ScanResult(
                    server_id=srv.id, check_item_id=r.check_item_id, scan_run_id=run.id,
                    result=r.result, current_setting=r.current_setting,
                    recommendation=r.recommendation, score=r.score, checked_at=now,
                )
                for r in latest
            ]
            db.session.add_all(new_rows)
            run.completed = (run.completed or 0) + 1
            db.session.commit()
        run.status = "completed"
        run.finished_at = datetime.utcnow()
        db.session.commit()


# ---------------------------------------------------------------------------
# 실제 모드 (USE_REAL_ANSIBLE=True)
# ansible-runner로 diagnose.yml을 실행해 실제 대상 서버에 SSH 접속,
# 점검 스크립트 실행 -> JSON 결과 회수 -> DB 적재까지 수행한다.
# ---------------------------------------------------------------------------
def _parse_result_json(server, run_id):
    """
    scan_results/<hostname>.json (ansible fetch가 회수한 파일)을 읽어
    ScanResult row로 변환한다. 출력 형식 계약은 ansible/scripts/README.md 참고.
    반환값: (저장한 행 수, 경고 메시지 리스트)
    """
    path = SCAN_RESULTS_DIR / f"{server.hostname}.json"
    if not path.exists():
        return 0, [f"{server.hostname}: 결과 파일이 없습니다 ({path}). SSH 접속 또는 스크립트 실행 실패 가능성."]

    try:
        items = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return 0, [f"{server.hostname}: JSON 파싱 실패 ({e}). run_all.sh가 JSON 배열 외 다른 출력을 섞었을 수 있음."]

    now = datetime.utcnow()
    saved = 0
    warnings = []
    for item in items:
        code = item.get("check_id")
        ci = CheckItem.query.filter_by(code=code).first()
        if not ci:
            warnings.append(f"{server.hostname}: 알 수 없는 check_id '{code}' - catalog.py에 없어 건너뜀")
            continue
        result = item.get("result", "N/A")
        score = item.get("score")
        if score is None:
            score = ci.weight if result == "취약" else 0.0
        db.session.add(ScanResult(
            server_id=server.id, check_item_id=ci.id, scan_run_id=run_id,
            result=result,
            current_setting=item.get("current_setting"),
            recommendation=item.get("recommendation"),
            score=score, checked_at=now,
        ))
        saved += 1
    return saved, warnings


def _run_scan_real(app, run_id, server_ids):
    import ansible_runner  # USE_REAL_ANSIBLE=True일 때만 필요하므로 지연 임포트

    with app.app_context():
        run = db.session.get(ScanRun, run_id)
        servers = Server.query.filter(Server.id.in_(server_ids)).all()
        hostnames = [s.hostname for s in servers]

        inventory_path = generate_inventory(server_ids=server_ids)
        SCAN_RESULTS_DIR.mkdir(parents=True, exist_ok=True)

        def on_event(event):
            data = event.get("event_data", {})
            # "결과 JSON 회수" 태스크가 성공하면 그 호스트는 사실상 끝난 것으로 본다.
            if event.get("event") == "runner_on_ok" and data.get("task", "").startswith("결과 JSON 회수"):
                with app.app_context():
                    r = db.session.get(ScanRun, run_id)
                    r.completed = (r.completed or 0) + 1
                    db.session.commit()

        result = ansible_runner.run(
            private_data_dir=ANSIBLE_DIR,
            playbook=PLAYBOOK_RELATIVE_PATH,
            inventory=inventory_path,
            limit=",".join(hostnames),
            extravars={"target_hosts": ",".join(hostnames)},
            event_handler=on_event,
            quiet=True,
        )

        all_warnings = []
        for s in servers:
            _, warnings = _parse_result_json(s, run.id)
            all_warnings.extend(warnings)
        for w in all_warnings:
            app.logger.warning("[diagnosis] %s", w)

        run.status = "completed" if result.status == "successful" else "failed"
        run.finished_at = datetime.utcnow()
        db.session.commit()


@diagnosis_bp.route("/")
@login_required
def index():
    servers = Server.query.order_by(Server.id).all()
    runs = ScanRun.query.order_by(ScanRun.started_at.desc()).limit(10).all()
    server_map = {s.id: s for s in servers}
    active_run = ScanRun.query.filter_by(status="running").order_by(ScanRun.started_at.desc()).first()
    missing_ssh = servers_missing_ssh_config()
    return render_template(
        "diagnosis.html", servers=servers, runs=runs, server_map=server_map,
        active_run=active_run, missing_ssh=missing_ssh,
        use_real_ansible=current_app.config.get("USE_REAL_ANSIBLE", False),
    )


@diagnosis_bp.route("/run", methods=["POST"])
@login_required
def run_scan():
    if not _require_admin():
        return redirect(url_for("diagnosis.index"))

    selected = request.form.getlist("server_ids")
    if not selected:
        selected = [str(s.id) for s in Server.query.all()]
    server_ids = [int(x) for x in selected]

    use_real = current_app.config.get("USE_REAL_ANSIBLE", False)

    if use_real:
        missing = [s.hostname for s in Server.query.filter(Server.id.in_(server_ids)).all()
                   if not s.ssh_key_path]
        if missing:
            flash(f"SSH 키 경로가 설정되지 않은 서버가 있어 진단을 시작할 수 없습니다: {', '.join(missing)} "
                  f"(서버 수정 화면에서 먼저 설정하세요)", "danger")
            return redirect(url_for("diagnosis.index"))

    run = ScanRun(
        started_at=datetime.utcnow(), status="running",
        triggered_by=f"{current_user.display_name}({current_user.username})",
        server_ids=",".join(str(x) for x in server_ids),
        total=len(server_ids), completed=0,
    )
    db.session.add(run)
    db.session.commit()

    app_obj = current_app._get_current_object()

    if use_real:
        t = threading.Thread(target=_run_scan_real, args=(app_obj, run.id, server_ids), daemon=True)
    else:
        seconds = current_app.config.get("SCAN_SIMULATION_SECONDS_PER_SERVER", 1.2)
        t = threading.Thread(target=_run_scan_simulated, args=(app_obj, run.id, server_ids, seconds), daemon=True)
    t.start()

    return redirect(url_for("diagnosis.index", run_id=run.id))


@diagnosis_bp.route("/status/<int:run_id>")
@login_required
def status(run_id):
    run = ScanRun.query.get_or_404(run_id)
    server_ids = run.server_id_list()
    servers = Server.query.filter(Server.id.in_(server_ids)).all()
    return jsonify(dict(
        id=run.id, status=run.status, total=run.total, completed=run.completed,
        servers=[s.hostname for s in servers],
    ))
