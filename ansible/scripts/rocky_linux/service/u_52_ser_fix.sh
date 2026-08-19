#!/bin/bash
# ============================================================
# U-52 (중) Telnet 서비스 비활성화 - 조치 스크립트
# 분류: 서비스관리 | 대상: Rocky Linux (rocky)
# 주의: 설정 파일을 변경하는 경우 원본을 .bak_<시각> 으로 백업합니다.
#       운영 서버 적용 전 반드시 테스트 서버에서 먼저 검증하세요.
# 실행: sudo bash u_52_ser_fix.sh
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
FIX_ID="U-52"
CATEGORY="서비스관리"
RISK_LEVEL="중"

# ============================================================
# 2~4. 현재 상태 확인 후 필요 시 조치 실행
#   STATUS 값: 조치완료 | 조치불필요 | 조치실패 | 수동조치필요
# ============================================================
FIXED=0
if systemctl is-active --quiet telnet.socket 2>/dev/null; then
    systemctl stop telnet.socket >/dev/null 2>&1
    systemctl disable telnet.socket >/dev/null 2>&1
    FIXED=1
fi
if [ -f /etc/xinetd.d/telnet ] && grep -qiE '^\s*disable\s*=\s*no' /etc/xinetd.d/telnet 2>/dev/null; then
    cp -p /etc/xinetd.d/telnet /etc/xinetd.d/telnet.bak_$(date +%Y%m%d%H%M%S)
    sed -i 's/disable[[:space:]]*=[[:space:]]*no/disable = yes/' /etc/xinetd.d/telnet
    systemctl restart xinetd >/dev/null 2>&1
    FIXED=1
fi
if pgrep -x in.telnetd >/dev/null 2>&1 || pgrep -x telnetd >/dev/null 2>&1; then
    pkill -9 in.telnetd 2>/dev/null
    pkill -9 telnetd 2>/dev/null
    FIXED=1
fi

if [ $FIXED -eq 1 ]; then
    STATUS="조치완료"; ACTION="Telnet 서비스를 중지/비활성화함. SSH(sshd) 사용을 권장함"
else
    STATUS="조치불필요"; ACTION="Telnet 서비스가 이미 비활성 상태"
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
