#!/bin/bash
# ============================================================
# U-60 (중) SNMP Community String 복잡성 설정
# 분류: 서비스관리 | 대상: Rocky Linux (rocky)
# 근거: 2026 주요정보통신기반시설 기술적 취약점 분석평가 방법 상세가이드(KISA)
# 실행: sudo bash u_60_ser_check.sh
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
CHECK_ID="U-60"
CATEGORY="서비스관리"
EXPECTED_VALUE="public/private 미사용 및 복잡도 기준 충족"
RISK_LEVEL="중"

# ============================================================
# 2. 진단 명령 실행 / 3. 결과 처리 / 4. 양호·취약 판단
# ============================================================
if ! systemctl is-active --quiet snmpd 2>/dev/null; then
    STATUS="양호"; CURRENT_VALUE="SNMP 미사용"; EVIDENCE="snmpd 비활성"
elif [ ! -f /etc/snmp/snmpd.conf ]; then
    STATUS="수동확인 필요"; CURRENT_VALUE="설정파일 없음"; EVIDENCE="snmpd.conf 를 찾지 못함"
else
    WEAK="no"; CHECKED="no"; EVID=""
    while read -r cs; do
        [ -z "$cs" ] && continue
        CHECKED="yes"
        LEN=${#cs}
        if [ "$cs" = "public" ] || [ "$cs" = "private" ]; then
            WEAK="yes"; EVID="${EVID}기본값 사용(${cs}); "
        elif [ "$LEN" -lt 8 ]; then
            WEAK="yes"; EVID="${EVID}8자 미만(길이:${LEN}); "
        fi
    done < <(grep -E '^\s*(com2sec|rocommunity|rwcommunity)\b' /etc/snmp/snmpd.conf 2>/dev/null | awk '{print $3}')
    VALUE="checked=$CHECKED weak=$WEAK"
    CMD_RC=0
    if [ "$CHECKED" = "no" ]; then
        STATUS="수동확인 필요"; CURRENT_VALUE="community 설정 없음"; EVIDENCE="com2sec/rocommunity 설정을 찾지 못함(SNMPv3만 사용 중일 수 있음)"
    elif [ "$WEAK" = "yes" ]; then
        STATUS="취약"; CURRENT_VALUE="취약한 Community String 존재"; EVIDENCE="$EVID"
    else
        STATUS="양호"; CURRENT_VALUE="복잡도 기준 충족"; EVIDENCE="Community String이 복잡도 기준을 충족함"
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
