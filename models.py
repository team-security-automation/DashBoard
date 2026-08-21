# -*- coding: utf-8 -*-
"""
데이터 모델
------------
WBS(1.2 상세설계)에서 예정한 "JSON 응답 스키마 필드 확정(check_id~recommendation 등 11개 필드)"
및 착수보고서 3단 계층 아키텍처, KISA 점수 산출식(붙임4)을 반영해 아래와 같이 11개 핵심 필드를
갖는 ScanResult를 중심으로 설계했다.

    check_id, category, item_name, risk_level, result, current_setting,
    recommendation, score, server_id, os_scope, checked_at   (11개 필드)

실제 운영 환경에서는 Ansible이 회수한 JSON을 그대로 이 테이블에 적재하면 된다.
(현재는 MySQL 대신 SQLite로 기본 설정되어 있으며, config.py의 SQLALCHEMY_DATABASE_URI만
 바꾸면 그대로 MySQL로 전환된다.)
"""
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db

# 위험도(상/중/하) 차등 배점 - 붙임4 "취약점 분석·평가 점수 산출식 예시" 기준
RISK_WEIGHT = {"H": 10, "M": 8, "L": 6}
RISK_LABEL = {"H": "상", "M": "중", "L": "하"}

# ansible/scripts/ 밑에 이 이름 그대로의 폴더(rocky_linux/ubuntu)가 있어야 진단이 돈다.
# 서버 등록 폼(라디오)과 CSV 업로드 검증이 둘 다 이 목록 하나만 본다 - 오타로 그른
# os_family("rocky", "Rocky" 등)가 들어가면 등록은 성공해도 진단 시 조용히 스크립트를
# 못 찾는 문제가 있었다.
OS_FAMILIES = ["Rocky Linux", "Ubuntu"]

ROLE_LABEL = {
    "admin": "실무자(관리자)",
    "approver": "승인자",
    "viewer": "일반(조회)",
}


class User(UserMixin, db.Model):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    display_name = db.Column(db.String(50), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="viewer")  # admin/approver/viewer

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)

    @property
    def role_label(self):
        return ROLE_LABEL.get(self.role, self.role)

    def can_run_diagnosis(self):
        return self.role == "admin"

    def can_request_approval(self):
        return self.role == "admin"

    def can_decide_approval(self):
        return self.role == "approver"


class Server(db.Model):
    __tablename__ = "server"

    id = db.Column(db.Integer, primary_key=True)
    hostname = db.Column(db.String(100), nullable=False, unique=True)
    ip = db.Column(db.String(50), nullable=False)
    os_family = db.Column(db.String(20), nullable=False)   # Rocky / Ubuntu
    os_version = db.Column(db.String(20), nullable=False)  # 9 / 10 / 24.04 / 26.04
    role_desc = db.Column(db.String(100))                  # 예: 웹서버+DB
    business_name = db.Column(db.String(100))
    business_team = db.Column(db.String(100))
    owner = db.Column(db.String(50))
    asset_grade = db.Column(db.String(10), default="2등급")
    confidentiality = db.Column(db.Integer, default=2)
    integrity = db.Column(db.Integer, default=2)
    availability = db.Column(db.Integer, default=2)
    is_web_db = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # --- SSH 접속 정보 (Ansible 인벤토리 생성에 사용) ---------------------
    # 보안 원칙: 비밀번호를 DB에 평문 저장하지 않는다. 키 파일 자체는
    # 컨트롤 노드 로컬 경로(예: /etc/ansible/keys/rocky01.pem, 권한 600)에
    # 두고, DB에는 "그 경로가 어디인지"만 저장한다.
    ssh_user = db.Column(db.String(50), default="ansible")
    ssh_port = db.Column(db.Integer, default=22)
    ssh_key_path = db.Column(db.String(255))  # 컨트롤 노드 기준 절대경로
    ssh_become = db.Column(db.Boolean, default=True)  # sudo(become:yes) 필요 여부

    scan_results = db.relationship(
        "ScanResult", backref="server", lazy="dynamic", cascade="all,delete-orphan"
    )
    # 서버 삭제 시 승인요청/조치이력/점수스냅샷도 함께 지워야 한다.
    # (예전엔 scan_result만 cascade가 걸려 있어서, 서버를 지워도 이 세 테이블에는
    # server_id가 그대로 남았다 - SQLite가 지워진 id를 재사용하면서 다른 서버의
    # 이력인 것처럼 뒤섞이는 문제가 있었다.)
    approval_requests_cascade = db.relationship(
        "ApprovalRequest", backref="server", lazy="dynamic",
        cascade="all,delete-orphan", foreign_keys="ApprovalRequest.server_id",
    )
    action_histories_cascade = db.relationship(
        "ActionHistory", backref="server", lazy="dynamic",
        cascade="all,delete-orphan", foreign_keys="ActionHistory.server_id",
    )
    score_snapshots_cascade = db.relationship(
        "ScoreSnapshot", backref="server", lazy="dynamic",
        cascade="all,delete-orphan", foreign_keys="ScoreSnapshot.server_id",
    )

    @property
    def os_label(self):
        return f"{self.os_family} {self.os_version}"

    def latest_results(self):
        """항목별 최신 진단 결과만 (check_item_id 기준 최신 1건)"""
        sub = (
            db.session.query(
                ScanResult.check_item_id, db.func.max(ScanResult.checked_at).label("mx")
            )
            .filter(ScanResult.server_id == self.id)
            .group_by(ScanResult.check_item_id)
            .subquery()
        )
        return (
            ScanResult.query.join(
                sub,
                db.and_(
                    ScanResult.check_item_id == sub.c.check_item_id,
                    ScanResult.checked_at == sub.c.mx,
                ),
            )
            .filter(ScanResult.server_id == self.id)
            .all()
        )


class CheckItem(db.Model):
    __tablename__ = "check_item"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(10), unique=True, nullable=False)   # U-01, WEB-XS 등
    category = db.Column(db.String(50), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    risk_level = db.Column(db.String(1), nullable=False)  # H/M/L
    os_scope = db.Column(db.String(10), nullable=False)   # unix / web
    guide = db.Column(db.Text)   # 조치 방법 요약(가이드 기준)
    order_no = db.Column(db.Integer, default=0)

    @property
    def weight(self):
        return RISK_WEIGHT.get(self.risk_level, 0)

    @property
    def risk_label(self):
        return RISK_LABEL.get(self.risk_level, self.risk_level)


class ScanRun(db.Model):
    __tablename__ = "scan_run"

    id = db.Column(db.Integer, primary_key=True)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    finished_at = db.Column(db.DateTime)
    status = db.Column(db.String(20), default="running")  # running/completed/failed/cancelled
    triggered_by = db.Column(db.String(50))
    server_ids = db.Column(db.String(200))  # "1,2,3"
    total = db.Column(db.Integer, default=0)
    completed = db.Column(db.Integer, default=0)
    # 실패 시 사람이 읽을 수 있는 원인 요약 (실행 이력 팝업에 표시). 성공/중지 시엔 비움.
    fail_reason = db.Column(db.Text)

    def server_id_list(self):
        return [int(x) for x in self.server_ids.split(",") if x]


class ScanResult(db.Model):
    """
    11개 핵심 필드 (WBS "JSON 응답 스키마" 항목 참고):
    check_id, category, item_name, risk_level, result, current_setting,
    recommendation, score, server_id, os_scope, checked_at
    실제로는 check_item_id로 CheckItem을 참조해 code/category/item_name/risk_level/os_scope를
    정규화했다 (중복 저장 방지). 조회 시 check_item 관계를 통해 11개 필드가 모두 재구성된다.
    """

    __tablename__ = "scan_result"

    id = db.Column(db.Integer, primary_key=True)
    server_id = db.Column(db.Integer, db.ForeignKey("server.id"), nullable=False)
    check_item_id = db.Column(db.Integer, db.ForeignKey("check_item.id"), nullable=False)
    scan_run_id = db.Column(db.Integer, db.ForeignKey("scan_run.id"), nullable=True)

    result = db.Column(db.String(10), nullable=False)  # 양호/취약/N/A
    current_setting = db.Column(db.Text)   # 취약(현재설정) - 진단 스크립트 JSON의 current_value
    recommendation = db.Column(db.Text)    # 양호(조치 내용) / 조치 방법 - 진단 스크립트 JSON의 expected_value
    evidence = db.Column(db.Text)          # 양호/취약 판정 근거 - 진단 스크립트 JSON의 evidence
    score = db.Column(db.Float, default=0)  # 해당 항목 진단결과값(취약=배점, 양호=0)
    # 수동/자동 조치 여부 - 진단 스크립트 JSON의 is_auto_fixable(boolean)을
    # blueprints/diagnosis.py에서 auto/manual 문자열로 변환해 저장.
    # 스크립트가 값을 안 보내면 impact.default_remediation_type()으로 채워진다.
    remediation_type = db.Column(db.String(10), default="auto")  # auto/manual
    checked_at = db.Column(db.DateTime, default=datetime.utcnow)

    check_item = db.relationship("CheckItem")

    def to_dict(self):
        """11개 필드 표준 JSON 스키마 + remediation_type(수동/자동 조치 여부), evidence(판정 근거)로 직렬화"""
        ci = self.check_item
        return {
            "check_id": ci.code,
            "category": ci.category,
            "item_name": ci.name,
            "risk_level": ci.risk_level,
            "result": self.result,
            "current_setting": self.current_setting,
            "recommendation": self.recommendation,
            "score": self.score,
            "server_id": self.server_id,
            "os_scope": ci.os_scope,
            "checked_at": self.checked_at.isoformat() if self.checked_at else None,
            "remediation_type": self.remediation_type,
            "evidence": self.evidence,
        }


class ApprovalRequest(db.Model):
    __tablename__ = "approval_request"

    id = db.Column(db.Integer, primary_key=True)
    server_id = db.Column(db.Integer, db.ForeignKey("server.id"), nullable=False)
    check_item_id = db.Column(db.Integer, db.ForeignKey("check_item.id"), nullable=False)
    scan_result_id = db.Column(db.Integer, db.ForeignKey("scan_result.id"), nullable=False)

    requested_by = db.Column(db.String(50))
    requested_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default="pending")  # pending/approved/rejected
    # 요청 시점의 진단결과에서 그대로 가져온 값. 승인자가 "승인"을 누른 뒤의 동작(자동 조치 실행 vs
    # 수동 조치 안내)을 이 값 하나로 분기한다 - blueprints/approvals.py의 decide() 참고.
    remediation_type = db.Column(db.String(10), default="auto")  # auto/manual

    diff_before = db.Column(db.Text)
    diff_after = db.Column(db.Text)
    affected_service = db.Column(db.String(150))
    expected_score_delta = db.Column(db.Float)

    approver = db.Column(db.String(50))
    decided_at = db.Column(db.DateTime)
    reject_reason = db.Column(db.Text)
    approve_note = db.Column(db.Text)
    # 수동 조치를 완료 처리할 때 실무자가 "무엇을/어떻게 조치했는지" 남기는 필수 기록.
    # 자동 조치는 시스템이 그대로 실행하므로 이 값이 필요 없다 (None으로 남음).
    work_note = db.Column(db.Text)

    executed_at = db.Column(db.DateTime)
    backup_path = db.Column(db.String(200))

    before_score = db.Column(db.Float)
    after_score = db.Column(db.Float)

    check_item = db.relationship("CheckItem")


class ActionHistory(db.Model):
    __tablename__ = "action_history"

    id = db.Column(db.Integer, primary_key=True)
    approval_id = db.Column(db.Integer, db.ForeignKey("approval_request.id"))
    server_id = db.Column(db.Integer, db.ForeignKey("server.id"))
    check_item_id = db.Column(db.Integer, db.ForeignKey("check_item.id"))

    before_result = db.Column(db.String(10))
    after_result = db.Column(db.String(10))
    before_score = db.Column(db.Float)
    after_score = db.Column(db.Float)
    performed_by = db.Column(db.String(50))
    performed_at = db.Column(db.DateTime, default=datetime.utcnow)
    backup_path = db.Column(db.String(200))
    # 수동 조치 완료 처리 시 실무자가 남긴 조치 내용 (자동 조치는 None) - 조치 보고서의 근거 자료.
    work_note = db.Column(db.Text)

    check_item = db.relationship("CheckItem")
    approval = db.relationship("ApprovalRequest")


class ScoreSnapshot(db.Model):
    """이력 관리(시계열 추세)를 위한 일자별 점수 스냅샷"""

    __tablename__ = "score_snapshot"

    id = db.Column(db.Integer, primary_key=True)
    server_id = db.Column(db.Integer, db.ForeignKey("server.id"), nullable=True)  # null=전체 평균
    snapshot_date = db.Column(db.Date, nullable=False)
    score = db.Column(db.Float, nullable=False)
    grade = db.Column(db.String(10))
