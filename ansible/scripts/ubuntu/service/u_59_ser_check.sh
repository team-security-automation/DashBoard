#!/bin/bash
# ============================================================
# U-59 (상) 안전한 SNMP 버전 사용
# 분류: 서비스관리 | 대상: Ubuntu (ubuntu)
# 근거: 2026 주요정보통신기반시설 기술적 취약점 분석평가 방법 상세가이드(KISA)
# 실행: sudo bash u_59_ser_check.sh
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
CHECK_ID="U-59"
CATEGORY="서비스관리"
EXPECTED_VALUE="SNMPv3(인증+암호화) 이상 사용"
RISK_LEVEL="상"

# ============================================================
# 2. 진단 명령 실행 / 3. 결과 처리 / 4. 양호·취약 판단
# ============================================================
if ! systemctl is-active --quiet snmpd 2>/dev/null; then
    STATUS="양호"; CURRENT_VALUE="SNMP 미사용"; EVIDENCE="snmpd 비활성"
elif [ ! -f /etc/snmp/snmpd.conf ]; then
    STATUS="수동확인 필요"; CURRENT_VALUE="설정파일 없음"; EVIDENCE="snmpd 활성이나 /etc/snmp/snmpd.conf 를 찾지 못함"
else
    V1V2=$(grep -E '^\s*(com2sec|rocommunity|rwcommunity)\b' /etc/snmp/snmpd.conf 2>/dev/null | head -1)
    V3=$(grep -E '^\s*createUser\b' /etc/snmp/snmpd.conf 2>/dev/null | head -1)
    VALUE="v1v2=[${V1V2}] v3=[${V3}]"
    CMD_RC=0
    if [ -n "$V1V2" ]; then
        STATUS="취약"; CURRENT_VALUE="$V1V2"; EVIDENCE="SNMP v1/v2c 설정이 발견됨"
    elif [ -n "$V3" ]; then
        STATUS="양호"; CURRENT_VALUE="SNMPv3 사용자 존재"; EVIDENCE="SNMPv3 설정이 확인됨"
    else
        STATUS="수동확인 필요"; CURRENT_VALUE="버전 판별 불가"; EVIDENCE="SNMP 버전 설정을 자동으로 판별하지 못함"
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
