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
    ("점검 스크립트 로컬 압축 (전송 파일 수 최소화)", 2),
    ("점검 스크립트 압축 파일 전송", 12),
    ("점검 스크립트 원격 압축 해제", 4),
    ("로컬 임시 압축파일 삭제", 2),
    ("점검 스크립트 일괄 실행 (표준 JSON 출력)", 55),
    ("결과 JSON 회수 (컨트롤 노드로)", 10),
    ("원격 작업 디렉터리 삭제 (흔적 미잔존)", 5),
]
_REAL_TASK_CUM = {}
_REAL_TASK_INDEX = {}
_c = 0
for _i, (_name, _w) in enumerate(REAL_TASK_WEIGHTS, start=1):
    _c += _w
    _REAL_TASK_CUM[_name] = _c
    _REAL_TASK_INDEX[_name] = _i
del _c, _i, _name, _w
REAL_TASK_TOTAL_STEPS = len(REAL_TASK_WEIGHTS)

SCAN_RESULTS_DIR = Path(ANSIBLE_DIR).parent / "scan_results"
PLAYBOOK_RELATIVE_PATH = "playbooks/diagnose.yml"
SCRIPTS_ROOT = Path(ANSIBLE_DIR) / "scripts"
# playbooks/diagnose.yml의 remote_work_dir과 반드시 같은 값이어야 한다.
REMOTE_WORK_DIR = "/tmp/security_check"

_RUN_TASK_NAME = "점검 스크립트 일괄 실행 (표준 JSON 출력)"
# "이 태스크 시작 직전까지의 누적 %" - 목록에서 _RUN_TASK_NAME 앞까지의
# 가중치 합. 하드코딩 안 해서 앞단 태스크 구성이 바뀌어도 자동으로 맞는다.
_RUN_TASK_BASE = sum(w for n, w in REAL_TASK_WEIGHTS[:[n for n, _ in REAL_TASK_WEIGHTS].index(_RUN_TASK_NAME)])
_RUN_TASK_WEIGHT = dict(REAL_TASK_WEIGHTS)[_RUN_TASK_NAME]


def _os_group_name(server):
    return server.os_family.strip().lower().replace(" ", "_")


def _total_check_items(os_group):
    d = SCRIPTS_ROOT / os_group
    return sum(1 for _ in d.rglob("*_check.sh")) or 1


def _poll_item_progress(run_id, server, hostnames, stop_event):
    """
    "점검 스크립트 일괄 실행" 태스크는 ansible 입장에서 하나의 shell 명령이라
    끝나야만 이벤트가 오고, 그 안에서 67개 스크립트가 몇 개 끝났는지는 알 수
    없다. run_all.sh가 스크립트 하나 끝날 때마다 run_all.progress에 한 줄씩
    남기므로, 이 스레드가 별도 SSH로 그 줄 수를 주기적으로 세서(%) 갱신한다.
    ansible 플레이북 실행 자체와는 무관한 "곁다리 관찰용" 연결이라 실패해도
    (아직 파일이 없거나 등) 진단 자체에는 영향을 주지 않는다.
    """
    import subprocess

    # server(ORM 객체)의 속성을 여기서 미리 값으로 뽑아둔다. 이 스레드는 메인 스레드가
    # app_context를 빠져나가 DB 세션이 정리된 뒤에도 몇 초씩 더 살아있는데, 그 시점에
    # server.hostname 같은 속성에 접근하면 DetachedInstanceError로 죽었었다
    # (실제 진단 결과에는 영향 없는 곁다리 스레드지만 로그가 지저분해지고 그 서버의
    # 세부 진행률 표시가 중간에 멈추는 부작용이 있었다).
    hostname = server.hostname
    ssh_key_path = server.ssh_key_path
    ssh_port = server.ssh_port
    ssh_user = server.ssh_user
    ip = server.ip
    os_family = server.os_family

    os_group = os_family.strip().lower().replace(" ", "_")
    total_items = _total_check_items(os_group)
    remote_progress = f"{REMOTE_WORK_DIR}/{os_group}/run_all.progress"
    ssh_cmd = [
        "ssh", "-i", ssh_key_path,
        "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", "-o", "StrictHostKeyChecking=no",
        "-p", str(ssh_port or 22),
        f"{ssh_user}@{ip}",
        f"wc -l < {remote_progress} 2>/dev/null || echo 0",
    ]
    while not stop_event.wait(2):
        try:
            out = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=8)
            count = int((out.stdout or "0").strip() or 0)
        except Exception:
            continue
        frac = min(count / total_items, 1.0)
        candidate = _RUN_TASK_BASE + frac * _RUN_TASK_WEIGHT
        # 서버별로 독립된 진행 상태를 들고 있는다(host_detail) - 여러 서버가 동시에
        # 돌 때 한 서버의 이벤트가 다른 서버 진행률을 덮어써서 화면이 왔다갔다/역행하는
        # 문제가 있었다. 이제 서버마다 자기 자리에만 쓴다.
        prog = _SCAN_PROGRESS.setdefault(run_id, {"host_detail": {}, "hosts": hostnames})
        hd = prog.setdefault("host_detail", {})
        entry = hd.setdefault(hostname, {})
        current = entry.get("pct", 0)
        # 이미 ansible 이벤트로 이 태스크가 끝난 걸로 표시됐으면(>= base+weight)
        # 더 이상 이 폴러가 값을 되돌리지 않는다.
        if entry.get("status") != "완료" and current < _RUN_TASK_BASE + _RUN_TASK_WEIGHT:
            entry["pct"] = max(current, candidate)
            entry["status"] = "진행중"
            entry["task"] = f"{_RUN_TASK_NAME} ({count}/{total_items}항목)"
            entry["step_index"] = _REAL_TASK_INDEX[_RUN_TASK_NAME]
            entry["step_total"] = REAL_TASK_TOTAL_STEPS
            entry["item_done"] = count
            entry["item_total"] = total_items

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
        id_to_hostname = {s.id: s.hostname for s in Server.query.filter(Server.id.in_(server_ids)).all()}
        hostnames = [id_to_hostname.get(sid, f"#{sid}") for sid in server_ids]
        # 시뮬레이션은 서버를 순서대로 하나씩 처리하지만, 화면에는 실행 전(대기)/
        # 실행 중/완료 상태를 서버마다 각자 보여줘야 하니 미리 전부 "대기"로 깔아둔다.
        host_detail = {h: {"status": "대기"} for h in hostnames}
        _SCAN_PROGRESS[run_id] = {"host_detail": host_detail, "hosts": hostnames}
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

            host_detail[srv.hostname] = dict(
                status="진행중", cat_index=0, cat_total=cat_total,
                category=None, item_done=0, item_total=item_total,
                step_index=0, step_total=cat_total,
            )
            for cat_index, (cat, rows) in enumerate(by_cat.items(), start=1):
                if run_id in _CANCEL_REQUESTED:
                    break
                host_detail[srv.hostname].update(cat_index=cat_index, category=cat, step_index=cat_index)
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
                host_detail[srv.hostname]["item_done"] = item_done
                db.session.commit()

            host_detail[srv.hostname]["status"] = "완료"
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

        # 서버마다 독립된 진행칸(host_detail)을 미리 만들어둔다. ansible이 forks로
        # 여러 서버를 동시에 처리하면 이벤트가 서버 순서와 무관하게 뒤섞여 들어오는데,
        # 예전엔 이걸 하나의 공유 필드(current_server/step_index 등)에 덮어써서
        # 화면이 "서버가 왔다갔다"하거나 단계가 역행하는 것처럼 보였다.
        _SCAN_PROGRESS[run_id] = {"host_detail": {h: {"status": "대기"} for h in hostnames}, "hosts": hostnames}
        host_failures = {}

        def on_event(event):
            data = event.get("event_data", {})
            task_name = data.get("task", "")
            host = data.get("host") or data.get("remote_addr")
            ev = event.get("event")
            prog = _SCAN_PROGRESS.setdefault(run_id, {"host_detail": {}, "hosts": hostnames})
            hd = prog.setdefault("host_detail", {})
            if ev in ("runner_on_unreachable", "runner_on_failed") and host:
                res = data.get("res") or {}
                raw_msg = res.get("msg") or data.get("res", {}).get("stderr") or str(res)
                host_failures[host] = raw_msg
                entry = hd.setdefault(host, {})
                entry["status"] = "실패"
                entry["reason"] = _guide_for_failure(raw_msg)
            if ev == "runner_on_ok" and task_name in _REAL_TASK_CUM and host:
                entry = hd.setdefault(host, {})
                if entry.get("status") != "실패":
                    entry["status"] = "진행중"
                entry["task"] = task_name
                entry["step_index"] = _REAL_TASK_INDEX[task_name]
                entry["step_total"] = REAL_TASK_TOTAL_STEPS
                entry["pct"] = _REAL_TASK_CUM[task_name]
            # "결과 JSON 회수" 태스크가 성공하면 그 호스트는 사실상 끝난 것으로 본다.
            if ev == "runner_on_ok" and task_name.startswith("결과 JSON 회수") and host:
                entry = hd.setdefault(host, {})
                entry["status"] = "완료"
                entry["pct"] = 100
                with app.app_context():
                    r = db.session.get(ScanRun, run_id)
                    r.completed = (r.completed or 0) + 1
                    db.session.commit()

        # 점검 스크립트 실행 단계(전체의 55%)는 ansible 입장에서 하나의 shell
        # 태스크라 항목 단위 진행을 알 수 없다. 서버마다 별도 SSH로 옆에서
        # run_all.progress를 들여다보는 폴러를 하나씩 띄워서 세분화한다.
        pollers = []
        poll_stop = threading.Event()
        for s in servers:
            th = threading.Thread(
                target=_poll_item_progress, args=(run_id, s, hostnames, poll_stop), daemon=True
            )
            th.start()
            pollers.append(th)

        try:
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
                # 릴레이 경유 등으로 SSH 연결이 일시적으로 튕겨도 태스크 단위로
                # 자동 재시도하도록 (기존엔 1회 실패=전체 실패였다).
                envvars={"ANSIBLE_SSH_RETRIES": "3", "ANSIBLE_TIMEOUT": "30"},
            )
        finally:
            poll_stop.set()

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
    hostnames = [s.hostname for s in servers]
    prog = _SCAN_PROGRESS.get(run_id, {})
    host_detail_raw = prog.get("host_detail", {})
    # run이 끝나면 _SCAN_PROGRESS[run_id]가 정리(pop)되는데, 그 직후에 상태를 조회하면
    # host_detail_raw가 비어서 완료된 서버까지 "대기"로 잘못 보이는 레이스가 있었다.
    # run.status가 이미 종료 상태면 기록이 없는 서버는 그 결과를 그대로 물려받게 한다.
    fallback_status = {"completed": "완료", "failed": "실패", "cancelled": "대기"}.get(run.status, "대기")

    # 서버마다 독립된 진행 정보를 그대로 배열로 내려준다 - 프론트가 서버별로
    # 각자의 줄(레인)을 그릴 수 있게. (예전엔 "지금 보고 있는 서버 하나"만 있었음)
    hosts_detail = []
    pct_sum = 0
    for h in hostnames:
        d = host_detail_raw.get(h) or {"status": fallback_status}
        status_label = d.get("status", "대기")
        step_total = d.get("step_total") or 0
        step_index = d.get("step_index") or 0
        if status_label == "완료":
            pct = 100.0
        elif "pct" in d:
            pct = d["pct"]
        elif step_total:
            pct = round((step_index / step_total) * 100, 1)
        else:
            pct = 0.0
        pct_sum += pct
        hosts_detail.append(dict(
            hostname=h, status=status_label, task=d.get("task") or d.get("category"),
            step_index=step_index, step_total=step_total,
            item_done=d.get("item_done", 0), item_total=d.get("item_total", 0),
            percent=round(pct, 1), reason=d.get("reason"),
        ))
    percent = round(pct_sum / len(hostnames), 1) if hostnames else 0.0
    if run.status == "completed":
        percent = 100.0

    return jsonify(dict(
        id=run.id, status=run.status, total=run.total, completed=run.completed,
        servers=hostnames, percent=percent, hosts_detail=hosts_detail,
        fail_reason=run.fail_reason,
    ))
