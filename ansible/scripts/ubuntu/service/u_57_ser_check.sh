#!/bin/bash
# ============================================================
# U-57 (중) Ftpusers 파일 설정
# 분류: 서비스관리 | 대상: Ubuntu (ubuntu)
# 근거: 2026 주요정보통신기반시설 기술적 취약점 분석평가 방법 상세가이드(KISA)
# 실행: sudo bash u_57_ser_check.sh
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
CHECK_ID="U-57"
CATEGORY="서비스관리"
EXPECTED_VALUE="root 계정의 FTP 직접 접속 차단"
RISK_LEVEL="중"

# ============================================================
# 2. 진단 명령 실행 / 3. 결과 처리 / 4. 양호·취약 판단
# ============================================================
if ! systemctl is-active --quiet vsftpd 2>/dev/null && ! systemctl is-active --quiet proftpd 2>/dev/null; then
    STATUS="양호"; CURRENT_VALUE="FTP 미사용"; EVIDENCE="FTP 서비스 비활성"
else
    BLOCKED="no"; EVID=""
    if [ -f /etc/ftpusers ] && grep -qE '^\s*root\s*$' /etc/ftpusers 2>/dev/null; then
        BLOCKED="yes"; EVID="${EVID}/etc/ftpusers 에 root 등록됨; "
    fi
    if [ -f "/etc/proftpd/proftpd.conf" ] && grep -qiE '^\s*RootLogin\s+off' "/etc/proftpd/proftpd.conf" 2>/dev/null; then
        BLOCKED="yes"; EVID="${EVID}proftpd RootLogin off 설정; "
    fi
    VALUE="blocked=$BLOCKED"
    CMD_RC=0
    if [ "$BLOCKED" = "yes" ]; then
        STATUS="양호"; CURRENT_VALUE="root 접속 차단됨"; EVIDENCE="$EVID"
    else
        STATUS="취약"; CURRENT_VALUE="root 접속 차단 미설정"; EVIDENCE="root 계정의 FTP 직접 접속 차단 설정을 찾지 못함"
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
