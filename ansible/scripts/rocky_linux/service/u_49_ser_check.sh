#!/bin/bash
# ============================================================
# U-49 (상) DNS 보안 버전 패치
# 분류: 서비스관리 | 대상: Rocky Linux (rocky)
# 근거: 2026 주요정보통신기반시설 기술적 취약점 분석평가 방법 상세가이드(KISA)
# 실행: sudo bash u_49_ser_check.sh
# ============================================================

# JSON 이스케이프 유틸 (따옴표/개행 처리)
json_esc() {
    local s="$1"
    s="${s//\\/\\\\}"
    s="${s//\"/\\\"}"
    s="$(printf '%s' "$s" | tr '\n' ' ')"
    printf '%s' "$s"
}

# ============================================================
# 1. 기본 정보
# ============================================================
CHECK_ID="U-49"
CATEGORY="서비스관리"
EXPECTED_VALUE="DNS 미사용 또는 최신 버전으로 주기적 패치 관리 중"
RISK_LEVEL="상"

# ============================================================
# 2. 진단 명령 실행 / 3. 결과 처리 / 4. 양호·취약 판단
# ============================================================
BIND_INSTALLED="no"
rpm -q bind >/dev/null 2>&1 && BIND_INSTALLED="yes"
command -v named >/dev/null 2>&1 && BIND_INSTALLED="yes"

BIND_ACTIVE="no"
for svc in "named"; do
    systemctl is-active --quiet "$svc" 2>/dev/null && BIND_ACTIVE="yes"
done

VALUE="installed=${BIND_INSTALLED} active=${BIND_ACTIVE}"
CMD_RC=0

if [ "$BIND_INSTALLED" = "no" ]; then
    STATUS="양호"
    CURRENT_VALUE="BIND 미설치"
    EVIDENCE="DNS(BIND) 서비스가 설치되어 있지 않아 해당 없음"
elif [ "$BIND_ACTIVE" = "no" ]; then
    STATUS="양호"
    CURRENT_VALUE="BIND 설치됨, 서비스 비활성"
    EVIDENCE="named 서비스가 비활성 상태"
else
    NAMED_VER=$(named -v 2>/dev/null)
    STATUS="수동확인 필요"
    CURRENT_VALUE="BIND 활성 (버전: ${NAMED_VER:-확인불가})"
    EVIDENCE="DNS 서비스 활성 중. ISC 취약점 목록(https://kb.isc.org/v1/docs/en/aa-00913) 대조 및 패치 정책 수립 여부는 수동 확인 필요"
fi

# ============================================================
# 5. JSON 출력
# ============================================================
cat <<EOF
{
  "check_id": "$(json_esc "$CHECK_ID")",
  "category": "$(json_esc "$CATEGORY")",
  "status": "$(json_esc "$STATUS")",
  "current_value": "$(json_esc "$CURRENT_VALUE")",
  "expected_value": "$(json_esc "$EXPECTED_VALUE")",
  "evidence": "$(json_esc "$EVIDENCE")",
  "hostname": "$(hostname)",
  "risk_level": "$(json_esc "$RISK_LEVEL")"
}
EOF

# ============================================================
# 6. 정상 종료
# ============================================================
exit 0
