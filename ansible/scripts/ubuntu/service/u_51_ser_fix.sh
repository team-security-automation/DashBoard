#!/bin/bash
# ============================================================
# U-51 (중) DNS 서비스의 취약한 동적 업데이트 설정 금지 - 조치 스크립트
# 분류: 서비스관리 | 대상: Ubuntu (ubuntu)
# 주의: 설정 파일을 변경하는 경우 원본을 .bak_<시각> 으로 백업합니다.
#       운영 서버 적용 전 반드시 테스트 서버에서 먼저 검증하세요.
# 실행: sudo bash u_51_ser_fix.sh
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
FIX_ID="U-51"
CATEGORY="서비스관리"
RISK_LEVEL="중"

# ============================================================
# 2~4. 현재 상태 확인 후 필요 시 조치 실행
#   STATUS 값: 조치완료 | 조치불필요 | 조치실패 | 수동조치필요
# ============================================================
BIND_ACTIVE="no"
for svc in "named" "bind9"; do
    systemctl is-active --quiet "$svc" 2>/dev/null && BIND_ACTIVE="yes"
done

CONF=""
for f in "/etc/bind/named.conf.options" "/etc/bind/named.conf"; do
    [ -f "$f" ] && { CONF="$f"; break; }
done

if [ "$BIND_ACTIVE" = "no" ] || [ -z "$CONF" ]; then
    STATUS="조치불필요"
    ACTION="DNS 미사용 또는 설정파일 미탐지로 조치 대상 아님"
else
    LINE=$(grep -i 'allow-update' "$CONF" 2>/dev/null | head -1)
    if [ -z "$LINE" ] || echo "$LINE" | grep -qE '\bnone\b'; then
        STATUS="조치불필요"
        ACTION="이미 동적 업데이트가 비활성/제한 상태임"
    else
        cp -p "$CONF" "${CONF}.bak_$(date +%Y%m%d%H%M%S)"
        sed -i "s|allow-update[^;]*;|allow-update { none; };|" "$CONF"
        systemctl reload bind9 >/dev/null 2>&1 || systemctl restart bind9 >/dev/null 2>&1
        STATUS="조치완료"
        ACTION="allow-update { none; }; 로 동적 업데이트를 비활성화함. 원본은 ${CONF}.bak_* 로 백업됨"
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
