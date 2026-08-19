# -*- coding: utf-8 -*-
"""
보안 점수 산출 로직
--------------------
근거: 미래창조과학부고시 제2013-37호
      (프로젝트 참고자료 "등급계산참고_취약점 분석·평가 점수 산출식 예시" 붙임4)

배점(위험도 차등):  상(H)=10점 / 중(M)=8점 / 하(L)=6점
진단결과값:
    ○ (취약점 발견)         : 배점 그대로
    × (취약점 제거=양호)     : 0점
    P (일부만 제거=부분조치) : 상 5점 / 중 4점 / 하 3점  (배점의 절반)

보안수준 = [(전체 취약점 점수합 − 식별된 취약점 점수합) / 전체 점수합] × 100

등급:
    91점 이상  : 우수
    81 ~ 90    : 양호
    71 ~ 80    : 보통
    61 ~ 70    : 미흡
    60점 이하  : 취약

N/A(해당 없음) 항목은 분모(전체 점수합)에서 제외한다.
"""

from models import RISK_WEIGHT

PARTIAL_RATIO = 0.5  # 'P'(일부 조치) 진단결과값 = 배점의 50%


def item_score_value(risk_level: str, result: str) -> float:
    """개별 항목의 '식별된 취약점 점수'(진단결과값)를 반환한다."""
    weight = RISK_WEIGHT.get(risk_level, 0)
    if result == "취약":
        return weight
    if result == "부분":
        return weight * PARTIAL_RATIO
    return 0.0  # 양호 / N/A


def grade_of(score: float) -> str:
    if score >= 91:
        return "우수"
    if score >= 81:
        return "양호"
    if score >= 71:
        return "보통"
    if score >= 61:
        return "미흡"
    return "취약"


GRADE_COLOR = {
    "우수": "good",
    "양호": "good",
    "보통": "warn",
    "미흡": "bad",
    "취약": "bad",
}


def calc_security_level(scan_results):
    """
    scan_results: ScanResult 객체 리스트(같은 서버의 최신 진단 결과 1세트)
    반환: (보안수준 점수(0~100, float), 등급 문자열, 전체점수합, 식별된점수합)
    """
    total = 0.0
    identified = 0.0
    for r in scan_results:
        ci = r.check_item
        if r.result == "N/A":
            continue
        total += ci.weight
        identified += item_score_value(ci.risk_level, r.result)

    if total == 0:
        return 0.0, "-", 0.0, 0.0

    level = (total - identified) / total * 100
    level = round(level, 1)
    return level, grade_of(level), total, identified
