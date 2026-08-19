#!/bin/bash
# ============================================================
# U-60 (중) SNMP Community String 복잡성 설정 - 조치 스크립트
# 분류: 서비스관리 | 대상: Rocky Linux (rocky)
# 주의: 설정 파일을 변경하는 경우 원본을 .bak_<시각> 으로 백업합니다.
#       운영 서버 적용 전 반드시 테스트 서버에서 먼저 검증하세요.
# 실행: sudo bash u_60_ser_fix.sh
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
FIX_ID="U-60"
CATEGORY="서비스관리"
RISK_LEVEL="중"

# ============================================================
# 2~4. 현재 상태 확인 후 필요 시 조치 실행
#   STATUS 값: 조치완료 | 조치불필요 | 조치실패 | 수동조치필요
# ============================================================
if ! systemctl is-active --quiet snmpd 2>/dev/null; then
    STATUS="조치불필요"; ACTION="SNMP 서비스 미사용"
elif [ ! -f /etc/snmp/snmpd.conf ]; then
    STATUS="수동조치필요"; ACTION="snmpd.conf 를 찾지 못해 자동 조치 불가"
else
    if grep -qE '^\s*(com2sec|rocommunity|rwcommunity)\b.*(public|private)' /etc/snmp/snmpd.conf 2>/dev/null; then
        NEWSTR="Snmp$(tr -dc 'A-Za-z0-9' </dev/urandom | head -c 12)!"
        cp -p /etc/snmp/snmpd.conf /etc/snmp/snmpd.conf.bak_$(date +%Y%m%d%H%M%S)
        sed -i "s/\bpublic\b/${NEWSTR}/g; s/\bprivate\b/${NEWSTR}/g" /etc/snmp/snmpd.conf
        systemctl restart snmpd >/dev/null 2>&1
        STATUS="조치완료"
        ACTION="기본 Community String(public/private)을 임의 생성한 복잡한 문자열로 교체함(생성값은 /etc/snmp/snmpd.conf 에서 확인 후 관련 담당자에게 재공지 필요)"
    else
        STATUS="조치불필요"; ACTION="기본값(public/private) 사용이 확인되지 않음. 8자 미만 등 다른 사유는 수동 확인 필요"
    fi
fi

# ============================================================
# 5. JSON 출력
# ============================================================
cat <<EOF
{
  "fix_id": "$(json_esc "$FIX_ID")",
  "category": "$(json_esc "$CATEGORY")",
  "status": "$(json_esc "$STATUS")",
  "action": "$(json_esc "$ACTION")",
  "hostname": "$(hostname)",
  "risk_level": "$(json_esc "$RISK_LEVEL")"
}
EOF

# ============================================================
# 6. 정상 종료
# ============================================================
exit 0
