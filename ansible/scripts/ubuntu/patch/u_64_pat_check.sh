#!/bin/bash
# ============================================================
# U-64 (상) 주기적 보안 패치 및 벤더 권고사항 적용
# 분류: 패치관리 | 대상: Ubuntu (ubuntu)
# 근거: 2026 주요정보통신기반시설 기술적 취약점 분석평가 방법 상세가이드(KISA)
# 실행: sudo bash u_64_pat_check.sh
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
CHECK_ID="U-64"
CATEGORY="패치관리"
EXPECTED_VALUE="패치 적용 정책을 수립하여 주기적으로 관리 중"
RISK_LEVEL="상"

# ============================================================
# 2. 진단 명령 실행 / 3. 결과 처리 / 4. 양호·취약 판단
# ============================================================
PENDING=$(apt list --upgradable 2>/dev/null | grep -vc '^Listing')
AUTO="비활성"
systemctl is-active --quiet unattended-upgrades.service 2>/dev/null && AUTO="활성"
VALUE="pending=$PENDING auto=$AUTO"
CMD_RC=0

STATUS="수동확인 필요"
CURRENT_VALUE="대기 패치: ${PENDING}건, 자동업데이트: $AUTO"
EVIDENCE="패치 적용 정책(주기적 확인·적용 절차) 수립 여부는 문서/운영 기록 확인이 필요하여 수동확인으로 분류함"

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
