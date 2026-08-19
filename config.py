# -*- coding: utf-8 -*-
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "kisa-security-automation-dev-key")

    # 데모: SQLite. 운영 전환 시 아래 한 줄만 MySQL URI로 교체하면 된다.
    # 예) mysql+pymysql://user:password@127.0.0.1:3306/security_automation?charset=utf8mb4
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'security_automation.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # 진단 실행 시뮬레이션 속도 (초/서버) - USE_REAL_ANSIBLE=False일 때만 사용
    SCAN_SIMULATION_SECONDS_PER_SERVER = 1.2

    # True로 바꾸면 시뮬레이션 대신 실제 ansible-runner로 대상 서버에 SSH 접속해 진단한다.
    # 컨트롤 노드에 ansible-core/ansible-runner 설치 + 서버별 SSH 키 등록이 끝난 뒤 켤 것.
    # (환경변수 USE_REAL_ANSIBLE=true 로도 설정 가능)
    USE_REAL_ANSIBLE = os.environ.get("USE_REAL_ANSIBLE", "false").lower() == "true"
