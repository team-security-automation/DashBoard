#!/bin/bash
# ============================================================
# U-55 (중) FTP 계정 Shell 제한 - 조치 스크립트
# 분류: 서비스관리 | 대상: Ubuntu (ubuntu)
# 주의: 설정 파일을 변경하는 경우 원본을 .bak_<시각> 으로 백업합니다.
#       운영 서버 적용 전 반드시 테스트 서버에서 먼저 검증하세요.
# 실행: sudo bash u_55_ser_fix.sh
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
FIX_ID="U-55"
CATEGORY="서비스관리"
RISK_LEVEL="중"

# ============================================================
# 2~4. 현재 상태 확인 후 필요 시 조치 실행
#   STATUS 값: 조치완료 | 조치불필요 | 조치실패 | 수동조치필요
# ============================================================
LINE=$(grep '^ftp:' /etc/passwd 2>/dev/null)
if [ -z "$LINE" ]; then
    STATUS="조치불필요"; ACTION="ftp 계정이 존재하지 않음"
else
    SHELL_PATH=$(echo "$LINE" | cut -d: -f7)
    if echo "$SHELL_PATH" | grep -qE '(nologin|false)$'; then
        STATUS="조치불필요"; ACTION="이미 로그인 불가 쉘로 설정되어 있음: $SHELL_PATH"
    else
        usermod -s /usr/sbin/nologin ftp >/dev/null 2>&1
        FIX_RC=$?
        if [ $FIX_RC -eq 0 ]; then
            STATUS="조치완료"; ACTION="ftp 계정 쉘을 /usr/sbin/nologin 으로 변경함"
        else
            STATUS="조치실패"; ACTION="usermod 실행 실패"
        fi
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
