# -*- coding: utf-8 -*-
"""
데모용 시드 데이터.

실제 운영 시에는 이 스크립트 대신 Ansible이 회수한 JSON이 ScanResult 테이블에 적재된다.
여기서는 착수보고서의 인프라 구성(로키 2대, 우분투 2대, 웹서버+DB 1대)과
KISA 점수 산출식을 그대로 반영한 "그럴듯한" 진단 결과를 생성해 대시보드 각 화면을
실제 데이터로 확인할 수 있게 한다.
"""
import random
from datetime import datetime, timedelta, date

from extensions import db
from models import (
    User, Server, CheckItem, ScanRun, ScanResult,
    ApprovalRequest, ActionHistory, ScoreSnapshot,
)
from catalog import UNIX_ITEMS, WEB_ITEMS
from scoring import calc_security_level

random.seed(42)

# ---------------------------------------------------------------------------
# 서버별 "현재 취약" 항목 코드 목록 (나머지는 전부 양호로 처리)
# ---------------------------------------------------------------------------
VULN_MAP = {
    "rocky01": ["U-06", "U-30", "U-47"],
    "rocky02": ["U-01", "U-04", "U-16", "U-23", "U-08", "U-13", "U-30", "U-42", "U-07", "U-09", "U-33"],
    "ubuntu01": ["U-33"],
    "ubuntu02": ["U-08", "U-30", "U-07", "U-09", "U-33"],
    "webdb01_unix": ["U-01", "U-02", "U-16", "U-25", "U-45", "U-08", "U-42", "U-43"],
    "webdb01_web": ["WEB-XS", "WEB-SI", "WEB-SN", "WEB-CC", "WEB-AE"],
}

# 이미 조치 완료되어 현재는 양호이지만, 이력에는 취약->양호 전환 기록이 남아있는 항목
REMEDIATED = {
    "rocky02": [("U-11", "실무자 su 대상자 sudoers 그룹 재정비 완료")],
}

CURRENT_SETTING_TEXT = {
    "U-01": "PermitRootLogin 값이 yes로 설정되어 있어 root 계정 원격 접속이 허용됨 (sshd_config)",
    "U-02": "PASS_MIN_LEN이 5로 설정되어 있고 pam_pwquality 복잡도 검증이 비활성화되어 있음",
    "U-04": "/etc/shadow 권한이 644로 설정되어 있어 일반 계정도 읽기 가능",
    "U-06": "wheel 그룹 제한 없이 모든 계정이 su 명령 사용 가능",
    "U-07": "퇴사자 계정 2건(test01, guest)이 삭제되지 않고 남아있음",
    "U-08": "wheel 그룹에 업무 무관 계정 3건이 포함되어 있음",
    "U-09": "/etc/group에 계정이 존재하지 않는 GID 3건 발견",
    "U-11": "미사용 계정의 Shell이 /bin/bash로 설정되어 로그인 가능",
    "U-13": "/etc/login.defs ENCRYPT_METHOD이 MD5로 설정됨",
    "U-16": "/etc/passwd 권한이 666으로 설정되어 있어 임의 수정 가능",
    "U-23": "SUID 설정된 불필요한 바이너리 4건 발견 (/usr/bin/chsh 등)",
    "U-25": "world writable 파일 12건 발견 (/tmp 하위 스크립트 포함)",
    "U-29": "/etc/hosts.lpd 권한이 644로 설정됨",
    "U-30": "/etc/profile에 UMASK 설정이 없음(기본값이 022 미만으로 적용됨)",
    "U-33": "용도를 알 수 없는 숨김 디렉터리(.old_backup)가 발견됨",
    "U-42": "SNMP Community String이 기본값 'public'으로 설정됨",
    "U-43": "Sendmail 릴레이 제한 설정이 없어 Open Relay로 악용 가능",
    "U-45": "Apache DocumentRoot에 Indexes 옵션이 활성화되어 디렉터리 목록이 노출됨",
    "U-47": "로그 파일(/var/log/secure) 권한이 644를 초과하는 664로 설정됨",
    "WEB-XS": "게시판 검색어 입력값 이스케이프 처리가 없어 스크립트 삽입 시 그대로 실행됨",
    "WEB-SI": "로그인 폼 파라미터에 Prepared Statement 미적용, 인증 우회 구문 입력 시 우회 확인됨",
    "WEB-SN": "로그인·회원정보 페이지가 HTTP(평문)로 서비스되고 있음",
    "WEB-CC": "세션 쿠키에 HttpOnly, Secure 옵션이 설정되어 있지 않음",
    "WEB-AE": "관리자 페이지가 /admin 경로로 별도 접근 제한 없이 노출되어 있음",
}

SERVERS = [
    dict(key="rocky01", hostname="rocky01", ip="10.0.10.11", os_family="Rocky Linux", os_version="9",
         role_desc="WAS", business_name="사내 포털 WAS", business_team="플랫폼운영팀", owner="이원찬",
         asset_grade="2등급", confidentiality=2, integrity=2, availability=2, is_web_db=False,
         ssh_key_path="/etc/ansible/keys/rocky01.pem"),
    dict(key="rocky02", hostname="rocky02", ip="10.0.10.12", os_family="Rocky Linux", os_version="10",
         role_desc="배치 서버", business_name="야간 정산 배치", business_team="데이터운영팀", owner="나장원",
         asset_grade="3등급", confidentiality=2, integrity=3, availability=2, is_web_db=False,
         ssh_key_path="/etc/ansible/keys/rocky02.pem"),
    dict(key="ubuntu01", hostname="ubuntu01", ip="10.0.10.21", os_family="Ubuntu", os_version="24.04",
         role_desc="파일 서버", business_name="사내 공유 파일 서버", business_team="총무지원팀", owner="김규림",
         asset_grade="2등급", confidentiality=2, integrity=2, availability=1, is_web_db=False,
         ssh_key_path="/etc/ansible/keys/ubuntu01.pem"),
    dict(key="ubuntu02", hostname="ubuntu02", ip="10.0.10.22", os_family="Ubuntu", os_version="26.04",
         role_desc="모니터링 서버", business_name="통합 모니터링", business_team="플랫폼운영팀", owner="노혜린",
         asset_grade="2등급", confidentiality=1, integrity=2, availability=2, is_web_db=False,
         ssh_key_path="/etc/ansible/keys/ubuntu02.pem"),
    dict(key="webdb01", hostname="webdb01", ip="10.0.10.31", os_family="Rocky Linux", os_version="9",
         role_desc="웹서버+DB", business_name="대국민 서비스 웹/DB", business_team="대국민서비스팀", owner="이원찬",
         asset_grade="1등급", confidentiality=3, integrity=3, availability=3, is_web_db=True,
         ssh_key_path="/etc/ansible/keys/webdb01.pem"),
]

USERS = [
    dict(username="admin", display_name="이원찬", role="admin", password="admin123!"),
    dict(username="approver", display_name="팀장(승인자)", role="approver", password="approve123!"),
    dict(username="viewer", display_name="김규림", role="viewer", password="viewer123!"),
]


def _create_items():
    order = 0
    items = {}
    for code, category, name, risk, guide in UNIX_ITEMS:
        order += 1
        ci = CheckItem(code=code, category=category, name=name, risk_level=risk,
                        os_scope="unix", guide=guide, order_no=order)
        db.session.add(ci)
        items[code] = ci
    for code, category, name, risk, guide in WEB_ITEMS:
        order += 1
        ci = CheckItem(code=code, category=category, name=name, risk_level=risk,
                        os_scope="web", guide=guide, order_no=order)
        db.session.add(ci)
        items[code] = ci
    db.session.flush()
    return items


def _create_servers():
    servers = {}
    for s in SERVERS:
        srv = Server(
            hostname=s["hostname"], ip=s["ip"], os_family=s["os_family"], os_version=s["os_version"],
            role_desc=s["role_desc"], business_name=s["business_name"], business_team=s["business_team"],
            owner=s["owner"], asset_grade=s["asset_grade"], confidentiality=s["confidentiality"],
            integrity=s["integrity"], availability=s["availability"], is_web_db=s["is_web_db"],
            ssh_user="ansible", ssh_port=22, ssh_key_path=s.get("ssh_key_path"), ssh_become=True,
        )
        db.session.add(srv)
        servers[s["key"]] = srv
    db.session.flush()
    return servers


def _scan_results_for(server, item_list, vuln_codes, checked_at, run_id):
    rows = []
    for code, ci in item_list:
        is_vuln = code in vuln_codes
        result = "취약" if is_vuln else "양호"
        score = ci.weight if is_vuln else 0.0
        current_setting = CURRENT_SETTING_TEXT.get(code) if is_vuln else None
        recommendation = ci.guide if is_vuln else None
        rows.append(ScanResult(
            server_id=server.id, check_item_id=ci.id, scan_run_id=run_id,
            result=result, current_setting=current_setting, recommendation=recommendation,
            score=score, checked_at=checked_at,
        ))
    db.session.add_all(rows)


def _gen_history(server, base_score, days=14):
    """서버별 과거 점수 스냅샷(개선 추세를 보여주기 위해 완만한 상승 추세 + 노이즈)"""
    today = date.today()
    start = base_score - random.uniform(6, 12)
    start = max(start, 30)
    snaps = []
    for i in range(days, -1, -1):
        d = today - timedelta(days=i)
        progress = (days - i) / days
        noise = random.uniform(-1.5, 1.5)
        val = start + (base_score - start) * progress + noise
        val = round(max(0, min(100, val)), 1)
        from scoring import grade_of
        snaps.append(ScoreSnapshot(server_id=server.id, snapshot_date=d, score=val, grade=grade_of(val)))
    return snaps


def seed():
    db.drop_all()
    db.create_all()

    # 사용자
    for u in USERS:
        user = User(username=u["username"], display_name=u["display_name"], role=u["role"])
        user.set_password(u["password"])
        db.session.add(user)

    # 점검항목 카탈로그
    items = _create_items()
    unix_items = [(c, items[c]) for c, *_ in UNIX_ITEMS]
    web_items = [(c, items[c]) for c, *_ in WEB_ITEMS]

    # 서버
    servers = _create_servers()

    now = datetime.utcnow()
    latest_run = ScanRun(
        started_at=now - timedelta(minutes=6), finished_at=now - timedelta(minutes=1),
        status="completed", triggered_by="이원찬(admin)",
        server_ids=",".join(str(s.id) for s in servers.values()),
        total=len(servers), completed=len(servers),
    )
    db.session.add(latest_run)
    db.session.flush()

    # 과거 진단 실행 이력 (진단실행 화면의 "실행 이력" 표시용)
    for i, dt_off in enumerate([3, 7, 10], start=1):
        past = ScanRun(
            started_at=now - timedelta(days=dt_off, minutes=8),
            finished_at=now - timedelta(days=dt_off, minutes=1),
            status="completed", triggered_by="이원찬(admin)",
            server_ids=",".join(str(s.id) for s in servers.values()),
            total=len(servers), completed=len(servers),
        )
        db.session.add(past)

    # 서버별 최신 진단 결과 생성
    for key in ["rocky01", "rocky02", "ubuntu01", "ubuntu02"]:
        srv = servers[key]
        _scan_results_for(srv, unix_items, VULN_MAP[key], now - timedelta(minutes=1), latest_run.id)

    webdb = servers["webdb01"]
    _scan_results_for(webdb, unix_items, VULN_MAP["webdb01_unix"], now - timedelta(minutes=1), latest_run.id)
    _scan_results_for(webdb, web_items, VULN_MAP["webdb01_web"], now - timedelta(minutes=1), latest_run.id)

    db.session.flush()

    # 이미 조치 완료된 항목(양호로 반영)
    for key, fixes in REMEDIATED.items():
        srv = servers[key]
        for code, note in fixes:
            ci = items[code]
            row = ScanResult.query.filter_by(server_id=srv.id, check_item_id=ci.id).first()
            if row:
                row.result = "양호"
                row.score = 0.0
                row.current_setting = None
                row.recommendation = None
    db.session.flush()

    # 점수 스냅샷(이력 관리용) 계산
    total_now = 0.0
    total_cnt = 0
    for key, srv in servers.items():
        results = srv.latest_results()
        level, grade, total, identified = calc_security_level(results)
        db.session.add_all(_gen_history(srv, level))
        total_now += level
        total_cnt += 1
    overall_avg_now = round(total_now / total_cnt, 1) if total_cnt else 0

    # 전체 평균 스냅샷(server_id=None)
    today = date.today()
    start = max(overall_avg_now - 9, 30)
    for i in range(14, -1, -1):
        d = today - timedelta(days=i)
        progress = (14 - i) / 14
        noise = random.uniform(-1.0, 1.0)
        val = round(max(0, min(100, start + (overall_avg_now - start) * progress + noise)), 1)
        from scoring import grade_of
        db.session.add(ScoreSnapshot(server_id=None, snapshot_date=d, score=val, grade=grade_of(val)))

    db.session.flush()

    # --- 조치 승인 워크플로 데모 데이터 -------------------------------------
    def _mk_approval(server_key, code, status, requested_days_ago=0, decided_days_ago=None,
                      reason=None, approver=None):
        srv = servers[server_key]
        ci = items[code]
        sr = ScanResult.query.filter_by(server_id=srv.id, check_item_id=ci.id).first()
        req_at = now - timedelta(days=requested_days_ago, hours=2)
        ar = ApprovalRequest(
            server_id=srv.id, check_item_id=ci.id, scan_result_id=sr.id,
            requested_by="이원찬(admin)", requested_at=req_at, status=status,
            diff_before=f"- {ci.name} 현재 설정: {sr.current_setting or '(진단결과 없음)'}",
            diff_after=f"+ 가이드 권고 설정 적용: {ci.guide}",
            affected_service=srv.role_desc,
            expected_score_delta=ci.weight,
        )
        if decided_days_ago is not None:
            ar.decided_at = now - timedelta(days=decided_days_ago)
            ar.approver = approver or "팀장(approver)"
        if status == "rejected":
            ar.reject_reason = reason
        db.session.add(ar)
        return ar

    # 승인 대기중
    _mk_approval("webdb01", "WEB-XS", "pending", requested_days_ago=0)
    _mk_approval("rocky02", "U-01", "pending", requested_days_ago=0)

    # 반려됨
    _mk_approval("ubuntu02", "U-08", "rejected", requested_days_ago=2, decided_days_ago=1,
                 reason="wheel 그룹 계정 3건 중 배치 스크립트에서 사용 중인 계정 포함 확인. "
                        "업무팀 협의 후 재요청 필요.")

    db.session.flush()

    # 조치 이력(이미 실행 완료된 것) - REMEDIATED 항목과 매칭
    rocky02 = servers["rocky02"]
    u11 = items["U-11"]
    ah = ActionHistory(
        server_id=rocky02.id, check_item_id=u11.id,
        before_result="취약", after_result="양호",
        before_score=u11.weight, after_score=0.0,
        performed_by="팀장(approver) 승인 → 이원찬(admin) 실행",
        performed_at=now - timedelta(days=4, hours=3),
        backup_path="/backup/rocky02/2026-08-14_U-11.tar.gz",
    )
    db.session.add(ah)

    db.session.commit()


if __name__ == "__main__":
    from app import create_app
    app = create_app()
    with app.app_context():
        seed()
        print("시드 데이터 생성 완료.")
