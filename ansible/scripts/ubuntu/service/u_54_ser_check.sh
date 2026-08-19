#!/bin/bash
# ============================================================
# U-54 (중) 암호화되지 않는 FTP 서비스 비활성화
# 분류: 서비스관리 | 대상: Ubuntu (ubuntu)
# 근거: 2026 주요정보통신기반시설 기술적 취약점 분석평가 방법 상세가이드(KISA)
# 실행: sudo bash u_54_ser_check.sh
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
CHECK_ID="U-54"
CATEGORY="서비스관리"
EXPECTED_VALUE="평문 FTP 서비스 비활성화(SFTP/FTPS 권장)"
RISK_LEVEL="중"

# ============================================================
# 2. 진단 명령 실행 / 3. 결과 처리 / 4. 양호·취약 판단
# ============================================================
ACTIVE_LIST=""
systemctl is-active --quiet vsftpd 2>/dev/null    && ACTIVE_LIST="${ACTIVE_LIST}vsftpd "
systemctl is-active --quiet proftpd 2>/dev/null   && ACTIVE_LIST="${ACTIVE_LIST}proftpd "
systemctl is-active --quiet pure-ftpd 2>/dev/null && ACTIVE_LIST="${ACTIVE_LIST}pure-ftpd "
VALUE="active_services=[$ACTIVE_LIST]"
CMD_RC=0

if [ -z "$ACTIVE_LIST" ]; then
    STATUS="양호"; CURRENT_VALUE="평문 FTP 미구동"; EVIDENCE="vsftpd/proftpd/pure-ftpd 모두 비활성"
else
    STATUS="취약"; CURRENT_VALUE="구동 중: $ACTIVE_LIST"; EVIDENCE="평문 FTP 서비스가 활성 상태"
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
