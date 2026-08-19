#!/bin/bash
# ============================================================
# U-53 (하) FTP 서비스 정보 노출 제한
# 분류: 서비스관리 | 대상: Rocky Linux (rocky)
# 근거: 2026 주요정보통신기반시설 기술적 취약점 분석평가 방법 상세가이드(KISA)
# 실행: sudo bash u_53_ser_check.sh
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
CHECK_ID="U-53"
CATEGORY="서비스관리"
EXPECTED_VALUE="FTP 접속 배너에 서비스/버전 정보 노출 없음"
RISK_LEVEL="하"

# ============================================================
# 2. 진단 명령 실행 / 3. 결과 처리 / 4. 양호·취약 판단
# ============================================================
VSFTPD_ACTIVE="no"; PROFTPD_ACTIVE="no"
systemctl is-active --quiet vsftpd 2>/dev/null && VSFTPD_ACTIVE="yes"
systemctl is-active --quiet proftpd 2>/dev/null && PROFTPD_ACTIVE="yes"

if [ "$VSFTPD_ACTIVE" = "no" ] && [ "$PROFTPD_ACTIVE" = "no" ]; then
    STATUS="양호"; CURRENT_VALUE="FTP 미사용"; EVIDENCE="FTP 서비스 비활성"
elif [ "$VSFTPD_ACTIVE" = "yes" ] && [ -f "/etc/vsftpd/vsftpd.conf" ]; then
    VALUE=$(grep -iE '^\s*ftpd_banner' "/etc/vsftpd/vsftpd.conf" 2>/dev/null)
    CMD_RC=$?
    if [ -n "$VALUE" ]; then
        STATUS="양호"; CURRENT_VALUE="$VALUE"; EVIDENCE="vsftpd 배너가 커스터마이즈됨"
    else
        STATUS="취약"; CURRENT_VALUE="ftpd_banner 미설정"; EVIDENCE="vsftpd 기본 배너 사용으로 버전정보 노출 가능"
    fi
elif [ "$PROFTPD_ACTIVE" = "yes" ] && [ -f "/etc/proftpd.conf" ]; then
    VALUE=$(grep -iE 'ServerIdent' "/etc/proftpd.conf" 2>/dev/null)
    CMD_RC=$?
    if echo "$VALUE" | grep -qi 'off'; then
        STATUS="양호"; CURRENT_VALUE="$VALUE"; EVIDENCE="ProFTP ServerIdent off 설정됨"
    else
        STATUS="취약"; CURRENT_VALUE="${VALUE:-미설정}"; EVIDENCE="ServerIdent off 미설정으로 배너에 버전정보 노출 가능"
    fi
else
    STATUS="수동확인 필요"; CURRENT_VALUE="FTP 활성, 설정파일 미탐지"; EVIDENCE="FTP 데몬 종류/설정파일 위치 확인 필요"
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
