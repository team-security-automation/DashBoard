# -*- coding: utf-8 -*-
import json
import threading
import time
from collections import OrderedDict
from datetime import datetime
from pathlib import Path

from flask import Blueprint, render_template, request, redirect, url_for, jsonify, current_app, flash
from flask_login import login_required, current_user

from extensions import db
from models import Server, ScanRun, ScanResult, CheckItem
from inventory import generate_inventory, servers_missing_ssh_config, ANSIBLE_DIR
from impact import default_remediation_type

diagnosis_bp = Blueprint("diagnosis", __name__, url_prefix="/diagnosis")

# 카테고리 단위 진행률(서버 몇 대 중 몇 대 뿐 아니라, 지금 어느 서버의 어느
# 카테고리를 보는 중인지)은 진행 중에만 의미 있는 휘발성 정보라 DB 컬럼을
# 새로 추가하지 않고 프로세스 메모리에만 run_id 기준으로 들고 있는다.
_SCAN_PROGRESS = {}

# 웹에서 "진단 중지"를 누르면 run_id를 이 set에 넣어둔다. 실행 스레드(시뮬레이션/실제
# 둘 다)가 주기적으로 자기 run_id가 여기 있는지 확인해서 있으면 스스로 멈춘다.
_CANCEL_REQUESTED = set()

# ansible 실패 메시지는 실무자가 바로 원인을 못 알아보는 원문(영어, stack 형태)이라,
# 자주 나오는 패턴을 사람이 읽을 만한 가이드 문구로 바꿔서 팝업에 보여준다.
# (튜플 순서 중요 - 위에서부터 먼저 매치되는 걸 사용)
_FAILURE_GUIDES = [
    ("Connection timed out",
     "서버와 통신이 원활하지 않습니다 (네트워크 단절/방화벽 차단/서버 다운 가능성). "
     "대상 서버의 전원·네트워크 상태와 22번 포트 접근 가능 여부를 확인하세요."),
    ("Failed to connect to the host via ssh",
     "SSH 접속에 실패했습니다. 서버 주소·SSH 포트가 맞는지, 서버의 sshd 서비스가 살아있는지 확인하세요."),
    ("Permission denied",
     "SSH 인증에 실패했습니다. 등록된 SSH 키가 대상 서버의 authorized_keys에 맞게 등록되어 있는지 확인하세요."),
    ("Missing sudo password",
     "sudo 실행에 비밀번호를 요구하고 있습니다. 대상 서버에서 해당 계정에 NOPASSWD sudo 권한을 설정하세요."),
    ("No route to host",
     "서버까지 네트워크 경로가 없습니다. 서버가 켜져 있는지, 같은 네트워크(VPN 등)에 연결되어 있는지 확인하세요."),
    ("Name or service not known",
     "서버 주소를 찾을 수 없습니다. 인벤토리에 등록된 IP/호스트명이 올바른지 확인하세요."),
]


def _guide_for_failure(raw_msg):
    for pattern, guide in _FAILURE_GUIDES:
        if pattern in raw_msg:
            return guide
    return f"알 수 없는 오류로 실패했습니다. 원본 메시지: {raw_msg[:200]}"

# 실제 ansible 모드는 카테고리(점검항목) 단위 이벤트가 없어서 대신 diagnose.yml의
# 태스크 단계별로 가중치를 매겨 진행률(%)을 만든다. "점검 스크립트 일괄 실행"이
# 실제 점검 67개 항목을 다 도는 구간이라 압도적으로 오래 걸리므로 가중치를 크게 둔다.
# (이름은 playbooks/diagnose.yml의 task name과 정확히 일치해야 함)
REAL_TASK_WEIGHTS = [
    ("Gathering Facts", 5),
    ("원격 작업 디렉터리 생성", 5),
    ("대상 OS 점검 스크립트 복사", 10),
    ("공통 라이브러리 복사", 10),
    ("점검 스크립트 일괄 실행 (표준 JSON 출력)", 55),
    ("결과 JSON 회수 (컨트롤 노드로)", 10),
    ("원격 작업 디렉터리 삭제 (흔적 미잔존)", 5),
]
_REAL_TASK_CUM = {}
_c = 0
for _name, _w in REAL_TASK_WEIGHTS:
    _c += _w
    _REAL_TASK_CUM[_name] = _c
del _c, _name, _w

SCAN_RESULTS_DIR = Path(ANSIBLE_DIR).parent / "scan_results"
PLAYBOOK_RELATIVE_PATH = "playbooks/diagnose.yml"

# 점검 스크립트마다 "사람이 봐야 함" 상태를 다른 문구로 보낼 수 있어(수동확인 필요/
# 수동조치필요 등) 대시보드 표준값("수동확인")으로 맞춘다.
STATUS_ALIASES = {
    "수동확인 필요": "수동확인",
    "수동조치필요": "수동확인",
}


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
            if run_id in _CANCEL_REQUESTED:
                break
            srv = db.session.get(Server, sid)
            if srv is None:
                continue
            latest = srv.latest_results()
            now = datetime.utcnow()

            by_cat = OrderedDict()
            for r in latest:
                by_cat.setdefault(r.check_item.category, []).append(r)
            cat_total = len(by_cat) or 1
            item_total = len(latest)
            item_done = 0
            # 카테고리 하나가 너무 빨리 지나가면 진행 상황이 안 보이니 최소 대기시간을 둔다.
            per_cat_sleep = max(seconds_per_server / cat_total, 0.35)

            _SCAN_PROGRESS[run_id] = dict(
                server=srv.hostname, cat_index=0, cat_total=cat_total,
                category=None, item_done=0, item_total=item_total,
            )
            for cat_index, (cat, rows) in enumerate(by_cat.items(), start=1):
                if run_id in _CANCEL_REQUESTED:
                    break
                _SCAN_PROGRESS[run_id].update(cat_index=cat_index, category=cat)
                time.sleep(per_cat_sleep)
                new_rows = [
                    ScanResult(
                        server_id=srv.id, check_item_id=r.check_item_id, scan_run_id=run.id,
                        result=r.result, current_setting=r.current_setting,
                        recommendation=r.recommendation, evidence=r.evidence, score=r.score,
                        remediation_type=r.remediation_type, checked_at=now,
                    )
                    for r in rows
                ]
                db.session.add_all(new_rows)
                item_done += len(rows)
                _SCAN_PROGRESS[run_id]["item_done"] = item_done
                db.session.commit()

            run.completed = (run.completed or 0) + 1
            db.session.commit()
        run.status = "cancelled" if run_id in _CANCEL_REQUESTED else "completed"
        run.finished_at = datetime.utcnow()
        _SCAN_PROGRESS.pop(run_id, None)
        _CANCEL_REQUESTED.discard(run_id)
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
        # 점검 스크립트 팀 확정 필드명: status/current_value/expected_value/evidence/is_auto_fixable.
        # (구 버전 result/current_setting/recommendation로 보내는 스크립트도 있을 수 있어 함께 지원)
        result = item.get("status") or item.get("result", "N/A")
        # 담당자별로 "사람이 확인해야 함" 상태를 다르게 표기하는 스크립트가 있어
        # (예: U-49~63/U-64는 "수동확인 필요", 일부 fix 스크립트는 "수동조치필요") 대시보드가
        # 아는 표준값 "수동확인"으로 정규화한다. 안 그러면 점수·색상·승인요청 버튼이
        # 전부 "양호"로 취급해버려 사람이 봐야 할 항목이 조용히 안전한 것처럼 보인다.
        result = STATUS_ALIASES.get(result, result)
        current_setting = item.get("current_value", item.get("current_setting"))
        recommendation = item.get("expected_value", item.get("recommendation"))
        evidence = item.get("evidence")
        score = item.get("score")
        if score is None:
            score = ci.weight if result in ("취약", "수동확인") else 0.0
        # is_auto_fixable(boolean)을 대시보드 내부 표기인 remediation_type(auto/manual)로 변환한다.
        # (구 버전 remediation_type 문자열로 보내는 스크립트도 있을 수 있어 함께 지원)
        is_auto_fixable = item.get("is_auto_fixable")
        if isinstance(is_auto_fixable, bool):
            remediation_type = "auto" if is_auto_fixable else "manual"
        elif item.get("remediation_type") in ("auto", "manual"):
            remediation_type = item.get("remediation_type")
        else:
            remediation_type = default_remediation_type(code)
        db.session.add(ScanResult(
            server_id=server.id, check_item_id=ci.id, scan_run_id=run_id,
            result=result,
            current_setting=current_setting,
            recommendation=recommendation,
            evidence=evidence,
            score=score, remediation_type=remediation_type, checked_at=now,
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

        _SCAN_PROGRESS[run_id] = {"hosts": {}, "percent": 0}
        host_failures = {}

        def on_event(event):
            data = event.get("event_data", {})
            task_name = data.get("task", "")
            host = data.get("host") or data.get("remote_addr")
            ev = event.get("event")
            if ev in ("runner_on_unreachable", "runner_on_failed") and host:
                res = data.get("res") or {}
                raw_msg = res.get("msg") or data.get("res", {}).get("stderr") or str(res)
                host_failures[host] = raw_msg
            if event.get("event") == "runner_on_ok" and task_name in _REAL_TASK_CUM and host:
                prog = _SCAN_PROGRESS.setdefault(run_id, {"hosts": {}, "percent": 0})
                prog["hosts"][host] = _REAL_TASK_CUM[task_name]
                prog["current_server"] = host
                prog["task"] = task_name
                total_weight = 100 * len(hostnames) or 1
                prog["percent"] = round(
                    sum(prog["hosts"].get(h, 0) for h in hostnames) / total_weight * 100, 1
                )
            # "결과 JSON 회수" 태스크가 성공하면 그 호스트는 사실상 끝난 것으로 본다.
            if event.get("event") == "runner_on_ok" and task_name.startswith("결과 JSON 회수"):
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
            # 웹에서 "진단 중지"를 누르면 이 콜백이 True를 반환해서 ansible-runner가
            # 실행 중인 ansible-playbook 프로세스를 죽이고 빠져나온다.
            cancel_callback=lambda: run_id in _CANCEL_REQUESTED,
            quiet=True,
        )

        cancelled = run_id in _CANCEL_REQUESTED
        all_warnings = []
        if not cancelled:
            for s in servers:
                _, warnings = _parse_result_json(s, run.id)
                all_warnings.extend(warnings)
            for w in all_warnings:
                app.logger.warning("[diagnosis] %s", w)

        if cancelled:
            run.status = "cancelled"
        else:
            run.status = "completed" if result.status == "successful" else "failed"
            if run.status == "failed":
                reasons = [f"{host}: {_guide_for_failure(msg)}" for host, msg in host_failures.items()]
                # ansible 이벤트로 못 잡은 실패(예: 결과 JSON 파싱 실패)는 _parse_result_json 경고로 보충
                reasons += [f"{w}" for w in all_warnings if not any(host in w for host in host_failures)]
                run.fail_reason = "\n".join(reasons) or "원인 미상 - 상세 로그를 확인하세요."
        run.finished_at = datetime.utcnow()
        _SCAN_PROGRESS.pop(run_id, None)
        _CANCEL_REQUESTED.discard(run_id)
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


@diagnosis_bp.route("/stop/<int:run_id>", methods=["POST"])
@login_required
def stop_scan(run_id):
    if not _require_admin():
        return redirect(url_for("diagnosis.index"))

    run = ScanRun.query.get_or_404(run_id)
    if run.status == "running":
        _CANCEL_REQUESTED.add(run_id)
        flash("진단 중지를 요청했습니다. 진행 중인 단계가 끝나는 대로 멈춥니다.", "warning")
    return redirect(url_for("diagnosis.index"))


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
    prog = _SCAN_PROGRESS.get(run_id, {})
    percent = prog.get("percent")
    if percent is None and run.total:
        # 시뮬레이션 모드: 서버 완료 수만으로는 서버 1대짜리 실행이 끝날 때까지
        # 0%에 멈춰 보이니, 지금 서버 안에서 진행 중인 카테고리 비율도 더해준다.
        server_frac = (run.completed or 0) / run.total
        within_frac = 0
        if prog.get("item_total"):
            within_frac = (prog.get("item_done", 0) / prog["item_total"]) / run.total
        percent = round((server_frac + within_frac) * 100, 1)
    if run.status == "completed":
        percent = 100
    return jsonify(dict(
        id=run.id, status=run.status, total=run.total, completed=run.completed,
        servers=[s.hostname for s in servers],
        percent=percent,
        current_server=prog.get("server") or prog.get("current_server"),
        category=prog.get("category") or prog.get("task"),
        cat_index=prog.get("cat_index", 0),
        cat_total=prog.get("cat_total", 0),
        item_done=prog.get("item_done", 0),
        item_total=prog.get("item_total", 0),
        fail_reason=run.fail_reason,
    ))
