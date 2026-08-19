#!/bin/bash
# ============================================================
# U-62 (하) 로그인 시 경고 메시지 설정
# 분류: 서비스관리 | 대상: Ubuntu (ubuntu)
# 근거: 2026 주요정보통신기반시설 기술적 취약점 분석평가 방법 상세가이드(KISA)
# 실행: sudo bash u_62_ser_check.sh
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
CHECK_ID="U-62"
CATEGORY="서비스관리"
EXPECTED_VALUE="서버 및 원격서비스 로그온 시 경고 메시지 출력"
RISK_LEVEL="하"

# ============================================================
# 2. 진단 명령 실행 / 3. 결과 처리 / 4. 양호·취약 판단
# ============================================================
MISSING=""
for f in /etc/issue /etc/issue.net /etc/motd; do
    [ -s "$f" ] || MISSING="${MISSING}${f} "
done
VALUE="missing=[$MISSING]"
CMD_RC=0

if [ -z "$MISSING" ]; then
    STATUS="양호"; CURRENT_VALUE="경고 메시지 설정됨"; EVIDENCE="/etc/issue, /etc/issue.net, /etc/motd 모두 설정됨"
else
    STATUS="취약"; CURRENT_VALUE="미설정 파일: $MISSING"; EVIDENCE="일부 경고 메시지 파일이 비어 있음"
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
