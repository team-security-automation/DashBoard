#!/bin/bash
# ============================================================
# U-61 (상) SNMP Access Control 설정
# 분류: 서비스관리 | 대상: Ubuntu (ubuntu)
# 근거: 2026 주요정보통신기반시설 기술적 취약점 분석평가 방법 상세가이드(KISA)
# 실행: sudo bash u_61_ser_check.sh
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
CHECK_ID="U-61"
CATEGORY="서비스관리"
EXPECTED_VALUE="SNMP 접근이 특정 대역으로 제한됨"
RISK_LEVEL="상"

# ============================================================
# 2. 진단 명령 실행 / 3. 결과 처리 / 4. 양호·취약 판단
# ============================================================
if ! systemctl is-active --quiet snmpd 2>/dev/null; then
    STATUS="양호"; CURRENT_VALUE="SNMP 미사용"; EVIDENCE="snmpd 비활성"
elif [ ! -f /etc/snmp/snmpd.conf ]; then
    STATUS="수동확인 필요"; CURRENT_VALUE="설정파일 없음"; EVIDENCE="snmpd.conf 를 찾지 못함"
else
    VALUE=$(grep -E '^\s*(com2sec|rocommunity|rwcommunity)\b' /etc/snmp/snmpd.conf 2>/dev/null | head -1)
    CMD_RC=$?
    if [ -z "$VALUE" ]; then
        STATUS="수동확인 필요"; CURRENT_VALUE="설정 없음"; EVIDENCE="com2sec/rocommunity 설정을 찾지 못함"
    elif echo "$VALUE" | grep -qE '\bdefault\b|0\.0\.0\.0/0'; then
        STATUS="취약"; CURRENT_VALUE="$VALUE"; EVIDENCE="모든 호스트(default)로부터 SNMP 접근이 허용됨"
    else
        STATUS="양호"; CURRENT_VALUE="$VALUE"; EVIDENCE="SNMP 접근이 특정 대역으로 제한됨"
    fi
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
