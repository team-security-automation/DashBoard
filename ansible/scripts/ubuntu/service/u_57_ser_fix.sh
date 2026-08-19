#!/bin/bash
# ============================================================
# U-57 (중) Ftpusers 파일 설정 - 조치 스크립트
# 분류: 서비스관리 | 대상: Ubuntu (ubuntu)
# 주의: 설정 파일을 변경하는 경우 원본을 .bak_<시각> 으로 백업합니다.
#       운영 서버 적용 전 반드시 테스트 서버에서 먼저 검증하세요.
# 실행: sudo bash u_57_ser_fix.sh
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
FIX_ID="U-57"
CATEGORY="서비스관리"
RISK_LEVEL="중"

# ============================================================
# 2~4. 현재 상태 확인 후 필요 시 조치 실행
#   STATUS 값: 조치완료 | 조치불필요 | 조치실패 | 수동조치필요
# ============================================================
if ! systemctl is-active --quiet vsftpd 2>/dev/null && ! systemctl is-active --quiet proftpd 2>/dev/null; then
    STATUS="조치불필요"; ACTION="FTP 서비스 미사용"
else
    FIXED=0
    if [ -f /etc/ftpusers ]; then
        if ! grep -qE '^\s*root\s*$' /etc/ftpusers 2>/dev/null; then
            cp -p /etc/ftpusers /etc/ftpusers.bak_$(date +%Y%m%d%H%M%S)
            echo "root" >> /etc/ftpusers
            FIXED=1
        fi
    else
        echo "root" > /etc/ftpusers
        chown root:root /etc/ftpusers
        chmod 640 /etc/ftpusers
        FIXED=1
    fi
    if [ -f "/etc/proftpd/proftpd.conf" ] && ! grep -qiE '^\s*RootLogin\s+off' "/etc/proftpd/proftpd.conf" 2>/dev/null; then
        cp -p "/etc/proftpd/proftpd.conf" "/etc/proftpd/proftpd.conf.bak_$(date +%Y%m%d%H%M%S)"
        echo 'RootLogin off' >> "/etc/proftpd/proftpd.conf"
        systemctl restart proftpd >/dev/null 2>&1
        FIXED=1
    fi

    if [ $FIXED -eq 1 ]; then
        STATUS="조치완료"; ACTION="root 계정의 FTP 직접 접속을 차단함(/etc/ftpusers 및/또는 RootLogin off)"
    else
        STATUS="조치불필요"; ACTION="이미 root 계정 접속이 차단되어 있음"
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
