#!/bin/bash
# ============================================================
# U-55 (중) FTP 계정 Shell 제한
# 분류: 서비스관리 | 대상: Ubuntu (ubuntu)
# 근거: 2026 주요정보통신기반시설 기술적 취약점 분석평가 방법 상세가이드(KISA)
# 실행: sudo bash u_55_ser_check.sh
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
CHECK_ID="U-55"
CATEGORY="서비스관리"
EXPECTED_VALUE="ftp 계정에 로그인 불가 쉘(nologin/false) 부여"
RISK_LEVEL="중"

# ============================================================
# 2. 진단 명령 실행 / 3. 결과 처리 / 4. 양호·취약 판단
# ============================================================
LINE=$(grep '^ftp:' /etc/passwd 2>/dev/null)
VALUE="$LINE"
CMD_RC=$?

if [ -z "$LINE" ]; then
    STATUS="양호"; CURRENT_VALUE="ftp 계정 없음"; EVIDENCE="ftp 시스템 계정이 존재하지 않음"
else
    SHELL_PATH=$(echo "$LINE" | cut -d: -f7)
    if echo "$SHELL_PATH" | grep -qE '(nologin|false)$'; then
        STATUS="양호"; CURRENT_VALUE="$SHELL_PATH"; EVIDENCE="ftp 계정 쉘이 로그인 불가로 설정됨"
    else
        STATUS="취약"; CURRENT_VALUE="$SHELL_PATH"; EVIDENCE="ftp 계정 쉘이 로그인 가능한 쉘로 설정됨"
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
