#!/bin/bash
# ============================================================
# U-53 (하) FTP 서비스 정보 노출 제한 - 조치 스크립트
# 분류: 서비스관리 | 대상: Ubuntu (ubuntu)
# 주의: 설정 파일을 변경하는 경우 원본을 .bak_<시각> 으로 백업합니다.
#       운영 서버 적용 전 반드시 테스트 서버에서 먼저 검증하세요.
# 실행: sudo bash u_53_ser_fix.sh
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
FIX_ID="U-53"
CATEGORY="서비스관리"
RISK_LEVEL="하"

# ============================================================
# 2~4. 현재 상태 확인 후 필요 시 조치 실행
#   STATUS 값: 조치완료 | 조치불필요 | 조치실패 | 수동조치필요
# ============================================================
FIXED=0
if systemctl is-active --quiet vsftpd 2>/dev/null && [ -f "/etc/vsftpd.conf" ]; then
    if ! grep -qiE '^\s*ftpd_banner' "/etc/vsftpd.conf" 2>/dev/null; then
        cp -p "/etc/vsftpd.conf" "/etc/vsftpd.conf.bak_$(date +%Y%m%d%H%M%S)"
        echo 'ftpd_banner=Authorized access only.' >> "/etc/vsftpd.conf"
        systemctl restart vsftpd >/dev/null 2>&1
        FIXED=1
    fi
fi
if systemctl is-active --quiet proftpd 2>/dev/null && [ -f "/etc/proftpd/proftpd.conf" ]; then
    if grep -qiE 'ServerIdent' "/etc/proftpd/proftpd.conf" 2>/dev/null; then
        cp -p "/etc/proftpd/proftpd.conf" "/etc/proftpd/proftpd.conf.bak_$(date +%Y%m%d%H%M%S)"
        sed -i 's/ServerIdent.*/ServerIdent off/' "/etc/proftpd/proftpd.conf"
    else
        cp -p "/etc/proftpd/proftpd.conf" "/etc/proftpd/proftpd.conf.bak_$(date +%Y%m%d%H%M%S)"
        echo 'ServerIdent off' >> "/etc/proftpd/proftpd.conf"
    fi
    systemctl restart proftpd >/dev/null 2>&1
    FIXED=1
fi

if [ $FIXED -eq 1 ]; then
    STATUS="조치완료"; ACTION="FTP 배너에서 버전/서비스 정보가 노출되지 않도록 설정함"
else
    STATUS="조치불필요"; ACTION="FTP 미사용이거나 이미 배너가 적절히 설정되어 있음"
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
