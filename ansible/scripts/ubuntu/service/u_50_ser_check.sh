#!/bin/bash
# ============================================================
# U-50 (상) DNS Zone Transfer 설정
# 분류: 서비스관리 | 대상: Ubuntu (ubuntu)
# 근거: 2026 주요정보통신기반시설 기술적 취약점 분석평가 방법 상세가이드(KISA)
# 실행: sudo bash u_50_ser_check.sh
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
CHECK_ID="U-50"
CATEGORY="서비스관리"
EXPECTED_VALUE="Zone Transfer가 허가된 대상으로만 제한됨"
RISK_LEVEL="상"

# ============================================================
# 2. 진단 명령 실행 / 3. 결과 처리 / 4. 양호·취약 판단
# ============================================================
BIND_ACTIVE="no"
for svc in "named" "bind9"; do
    systemctl is-active --quiet "$svc" 2>/dev/null && BIND_ACTIVE="yes"
done

CONF=""
for f in "/etc/bind/named.conf.options" "/etc/bind/named.conf"; do
    [ -f "$f" ] && { CONF="$f"; break; }
done

if [ "$BIND_ACTIVE" = "no" ]; then
    STATUS="양호"; CURRENT_VALUE="DNS 서비스 미사용"; EVIDENCE="BIND 비활성 상태로 해당 없음"
elif [ -z "$CONF" ]; then
    STATUS="수동확인 필요"; CURRENT_VALUE="설정파일 미탐지"; EVIDENCE="BIND는 활성이나 named.conf 위치를 찾지 못함"
else
    VALUE=$(grep -i 'allow-transfer' "$CONF" 2>/dev/null | head -1)
    CMD_RC=$?
    if [ -z "$VALUE" ]; then
        STATUS="취약"
        CURRENT_VALUE="allow-transfer 설정 없음"
        EVIDENCE="$CONF 에 allow-transfer 설정이 없어 기본값(모든 호스트 허용)이 적용됨"
    elif echo "$VALUE" | grep -qE '\bany\b'; then
        STATUS="취약"
        CURRENT_VALUE="$VALUE"
        EVIDENCE="모든 호스트에 Zone Transfer가 허용됨"
    else
        STATUS="양호"
        CURRENT_VALUE="$VALUE"
        EVIDENCE="Zone Transfer 대상이 제한되어 있음"
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
