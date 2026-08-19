#!/bin/bash
# ============================================================
# U-62 (하) 로그인 시 경고 메시지 설정 - 조치 스크립트
# 분류: 서비스관리 | 대상: Ubuntu (ubuntu)
# 주의: 설정 파일을 변경하는 경우 원본을 .bak_<시각> 으로 백업합니다.
#       운영 서버 적용 전 반드시 테스트 서버에서 먼저 검증하세요.
# 실행: sudo bash u_62_ser_fix.sh
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
FIX_ID="U-62"
CATEGORY="서비스관리"
RISK_LEVEL="하"

# ============================================================
# 2~4. 현재 상태 확인 후 필요 시 조치 실행
#   STATUS 값: 조치완료 | 조치불필요 | 조치실패 | 수동조치필요
# ============================================================
BANNER_TEXT="본 시스템은 인가된 사용자만 이용할 수 있습니다. 무단 접근 시 관련 법률에 따라 처벌될 수 있습니다."
FIXED=0
for f in /etc/issue /etc/issue.net /etc/motd; do
    if [ ! -s "$f" ]; then
        echo "$BANNER_TEXT" > "$f"
        FIXED=1
    fi
done
if [ -f /etc/ssh/sshd_config ] && ! grep -qiE '^\s*Banner\s+/etc/issue.net' /etc/ssh/sshd_config 2>/dev/null; then
    cp -p /etc/ssh/sshd_config /etc/ssh/sshd_config.bak_$(date +%Y%m%d%H%M%S)
    if grep -qiE '^\s*#?\s*Banner\b' /etc/ssh/sshd_config 2>/dev/null; then
        sed -i 's|^[[:space:]]*#\?[[:space:]]*Banner.*|Banner /etc/issue.net|' /etc/ssh/sshd_config
    else
        echo 'Banner /etc/issue.net' >> /etc/ssh/sshd_config
    fi
    systemctl reload sshd >/dev/null 2>&1 || systemctl restart sshd >/dev/null 2>&1
    FIXED=1
fi

if [ $FIXED -eq 1 ]; then
    STATUS="조치완료"; ACTION="/etc/issue, /etc/issue.net, /etc/motd 에 경고 문구를 설정하고 sshd Banner 지시자를 적용함"
else
    STATUS="조치불필요"; ACTION="이미 모든 경고 메시지가 설정되어 있음"
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
