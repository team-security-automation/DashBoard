# -*- coding: utf-8 -*-
"""
조치 영향도 매핑
-----------------
승인자가 조치를 승인하기 전에 "이 조치가 서버에 어떤 영향을 주는지"를 참고할 수 있도록
점검항목 코드별 영향도를 정적으로 매핑한다. 실측(dry-run) 기반 동적 평가가 아니라,
항목 성격(설정 재적용/서비스 재시작/코드 배포 등)에 따라 미리 정의해둔 프로파일을
코드에 매칭하는 단순 조회 방식이다.
"""

IMPACT_LEVEL_LABEL = {"H": "상", "M": "중", "L": "하"}

# 영향 프로파일: 재시작/반영 방식과 영향 범위를 재사용 가능한 템플릿으로 정의
IMPACT_PROFILES = {
    "instant_low": {
        "apply": "즉시 적용 (재시작 불필요)",
        "scope": "설정 변경만으로 반영되며 서비스 중단이 발생하지 않습니다.",
    },
    "instant_auth": {
        "apply": "즉시 적용 (재시작 불필요)",
        "scope": "인증/권한 관련 파일이라 오설정 시 로그인·접근 장애로 이어질 수 있습니다.",
    },
    "session_reset": {
        "apply": "설정 즉시 반영",
        "scope": "적용 시점 이후 관련 계정의 로그인 세션·권한이 초기화될 수 있습니다.",
    },
    "service_restart_minor": {
        "apply": "서비스 재시작 필요",
        "scope": "재시작 구간 동안 수 초 내외의 짧은 순단이 발생할 수 있습니다.",
    },
    "service_restart_major": {
        "apply": "서비스 재시작 필요",
        "scope": "재시작 구간 동안 접속 중인 세션·트랜잭션이 끊어질 수 있습니다.",
    },
    "network_rule": {
        "apply": "접근제어 규칙 재적용",
        "scope": "규칙을 잘못 지정하면 정상 접근 트래픽까지 차단될 수 있습니다.",
    },
    "reboot_required": {
        "apply": "재부팅 권장",
        "scope": "커널·패치 적용 항목으로 재부팅 시 서버의 모든 서비스가 일시 중단됩니다.",
    },
    "app_deploy": {
        "apply": "애플리케이션 배포 필요",
        "scope": "코드 배포·재기동 구간 동안 서비스에 영향이 있으며 회귀 테스트가 권장됩니다.",
    },
}

# 점검항목 코드 -> (영향 프로파일, 영향도 등급 H/M/L)
CHECK_IMPACT_MAP = {
    # 계정 관리
    "U-01": ("service_restart_minor", "M"),
    "U-02": ("instant_low", "L"),
    "U-03": ("instant_auth", "M"),
    "U-04": ("instant_low", "L"),
    "U-05": ("session_reset", "M"),
    "U-06": ("instant_auth", "M"),
    "U-07": ("session_reset", "M"),
    "U-08": ("instant_auth", "M"),
    "U-09": ("instant_low", "L"),
    "U-10": ("instant_auth", "M"),
    "U-11": ("session_reset", "M"),
    "U-12": ("instant_low", "L"),
    "U-13": ("instant_low", "L"),
    # 파일 및 디렉터리 관리
    "U-14": ("instant_low", "L"),
    "U-15": ("instant_low", "L"),
    "U-16": ("instant_auth", "M"),
    "U-17": ("instant_auth", "M"),
    "U-18": ("instant_auth", "M"),
    "U-19": ("instant_low", "L"),
    "U-20": ("instant_low", "L"),
    "U-21": ("instant_low", "L"),
    "U-22": ("instant_low", "L"),
    "U-23": ("instant_auth", "M"),
    "U-24": ("instant_low", "L"),
    "U-25": ("instant_low", "L"),
    "U-26": ("instant_low", "L"),
    "U-27": ("instant_low", "L"),
    "U-28": ("network_rule", "H"),
    "U-29": ("instant_low", "L"),
    "U-30": ("instant_low", "L"),
    "U-31": ("instant_low", "L"),
    "U-32": ("instant_low", "L"),
    "U-33": ("instant_low", "L"),
    # 서비스 관리
    "U-34": ("service_restart_minor", "L"),
    "U-35": ("service_restart_minor", "M"),
    "U-36": ("service_restart_minor", "M"),
    "U-37": ("instant_low", "L"),
    "U-38": ("service_restart_minor", "L"),
    "U-39": ("service_restart_major", "H"),
    "U-40": ("network_rule", "M"),
    "U-41": ("service_restart_minor", "M"),
    "U-42": ("service_restart_minor", "M"),
    "U-43": ("service_restart_minor", "M"),
    "U-44": ("service_restart_major", "H"),
    "U-45": ("service_restart_major", "H"),
    # 패치/로그 관리
    "U-46": ("reboot_required", "H"),
    "U-47": ("service_restart_minor", "L"),
    # 웹 애플리케이션
    "WEB-CI": ("app_deploy", "H"),
    "WEB-SI": ("app_deploy", "H"),
    "WEB-DI": ("service_restart_minor", "L"),
    "WEB-EP": ("app_deploy", "M"),
    "WEB-IL": ("app_deploy", "M"),
    "WEB-XS": ("app_deploy", "H"),
    "WEB-CF": ("app_deploy", "H"),
    "WEB-SF": ("app_deploy", "H"),
    "WEB-BF": ("instant_auth", "M"),
    "WEB-IA": ("app_deploy", "H"),
    "WEB-IN": ("app_deploy", "H"),
    "WEB-PR": ("app_deploy", "M"),
    "WEB-PV": ("app_deploy", "H"),
    "WEB-FU": ("app_deploy", "H"),
    "WEB-FD": ("app_deploy", "M"),
    "WEB-IS": ("session_reset", "H"),
    "WEB-SN": ("service_restart_major", "H"),
    "WEB-CC": ("session_reset", "M"),
    "WEB-AE": ("service_restart_minor", "M"),
    "WEB-AU": ("app_deploy", "M"),
    "WEB-WM": ("service_restart_minor", "L"),
}

_DEFAULT_IMPACT = ("instant_low", "L")


def get_impact(check_code):
    """점검항목 코드에 대한 영향도 정보를 매핑 테이블에서 조회한다 (정적 매핑, 동적 산정 아님)."""
    profile_key, level = CHECK_IMPACT_MAP.get(check_code, _DEFAULT_IMPACT)
    profile = IMPACT_PROFILES[profile_key]
    return {
        "level": level,
        "level_label": IMPACT_LEVEL_LABEL[level],
        "apply": profile["apply"],
        "scope": profile["scope"],
    }


# ---------------------------------------------------------------------------
# 수동/자동 조치 여부 기본값
# ---------------------------------------------------------------------------
# 진단 스크립트가 JSON으로 "remediation_type"을 직접 보내주면 그 값을 그대로 신뢰한다
# (ansible/scripts/README.md 참고). 스크립트가 값을 안 보내는 경우(시뮬레이션 모드 포함)에만
# 이 영향 프로파일 기반 기본값으로 대체한다: 코드 배포(app_deploy)·재부팅(reboot_required)이
# 필요한 항목은 자동화 시 위험이 커서 기본을 "수동"으로 잡는다.
MANUAL_ONLY_PROFILES = {"app_deploy", "reboot_required"}


def default_remediation_type(check_code):
    profile_key, _ = CHECK_IMPACT_MAP.get(check_code, _DEFAULT_IMPACT)
    return "manual" if profile_key in MANUAL_ONLY_PROFILES else "auto"
