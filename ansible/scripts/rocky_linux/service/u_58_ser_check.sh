#!/bin/bash
# ============================================================
# U-58 (중) 불필요한 SNMP 서비스 구동 점검
# 분류: 서비스관리 | 대상: Rocky Linux (rocky)
# 근거: 2026 주요정보통신기반시설 기술적 취약점 분석평가 방법 상세가이드(KISA)
# 실행: sudo bash u_58_ser_check.sh
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
CHECK_ID="U-58"
CATEGORY="서비스관리"
EXPECTED_VALUE="SNMP 서비스 미사용"
RISK_LEVEL="중"

# ============================================================
# 2. 진단 명령 실행 / 3. 결과 처리 / 4. 양호·취약 판단
# ============================================================
VALUE=$(systemctl is-active snmpd 2>/dev/null)
CMD_RC=$?

if [ "$VALUE" = "active" ]; then
    STATUS="취약"; CURRENT_VALUE="snmpd 활성"; EVIDENCE="SNMP 서비스가 구동 중"
else
    STATUS="양호"; CURRENT_VALUE="snmpd 비활성"; EVIDENCE="SNMP 서비스가 비활성 상태"
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
