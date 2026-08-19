#!/bin/bash
# ============================================================
# U-56 (하) FTP 서비스 접근 제어 설정
# 분류: 서비스관리 | 대상: Ubuntu (ubuntu)
# 근거: 2026 주요정보통신기반시설 기술적 취약점 분석평가 방법 상세가이드(KISA)
# 실행: sudo bash u_56_ser_check.sh
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
CHECK_ID="U-56"
CATEGORY="서비스관리"
EXPECTED_VALUE="특정 IP/호스트만 FTP 접속 허용"
RISK_LEVEL="하"

# ============================================================
# 2. 진단 명령 실행 / 3. 결과 처리 / 4. 양호·취약 판단
# ============================================================
if ! systemctl is-active --quiet vsftpd 2>/dev/null && ! systemctl is-active --quiet proftpd 2>/dev/null; then
    STATUS="양호"; CURRENT_VALUE="FTP 미사용"; EVIDENCE="FTP 서비스 비활성"
else
    CONTROL="no"; EVID=""
    if [ -f /etc/hosts.allow ] && grep -qE 'vsftpd|proftpd|ftpd|^ALL' /etc/hosts.allow 2>/dev/null; then
        CONTROL="yes"; EVID="${EVID}hosts.allow 접근제어 존재; "
    fi
    if [ -f "/etc/vsftpd.conf" ] && grep -qiE '^\s*userlist_enable\s*=\s*YES' "/etc/vsftpd.conf" 2>/dev/null; then
        CONTROL="yes"; EVID="${EVID}vsftpd userlist_enable=YES; "
    fi
    if command -v ufw >/dev/null 2>&1 && ufw status 2>/dev/null | grep -qE '21/tcp'; then
        CONTROL="yes"; EVID="${EVID}ufw 21/tcp 규칙 존재; "
    fi
    if command -v firewall-cmd >/dev/null 2>&1 && firewall-cmd --list-services 2>/dev/null | grep -qw ftp; then
        CONTROL="yes"; EVID="${EVID}firewalld ftp 서비스 규칙 존재; "
    fi
    VALUE="control=$CONTROL"
    CMD_RC=0
    if [ "$CONTROL" = "yes" ]; then
        STATUS="양호"; CURRENT_VALUE="접근제어 존재"; EVIDENCE="$EVID"
    else
        STATUS="취약"; CURRENT_VALUE="접근제어 미탐지"; EVIDENCE="TCP Wrapper/userlist/방화벽 등 FTP 접근 제어 설정을 찾지 못함"
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
