#!/bin/bash
# ============================================================
# U-64 (상) 주기적 보안 패치 및 벤더 권고사항 적용 - 조치 스크립트
# 분류: 패치관리 | 대상: Ubuntu (ubuntu)
# 주의: 설정 파일을 변경하는 경우 원본을 .bak_<시각> 으로 백업합니다.
#       운영 서버 적용 전 반드시 테스트 서버에서 먼저 검증하세요.
# 실행: sudo bash u_64_pat_fix.sh
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
FIX_ID="U-64"
CATEGORY="패치관리"
RISK_LEVEL="상"

# ============================================================
# 2~4. 현재 상태 확인 후 필요 시 조치 실행
#   STATUS 값: 조치완료 | 조치불필요 | 조치실패 | 수동조치필요
# ============================================================
if systemctl is-active --quiet unattended-upgrades.service 2>/dev/null; then
    STATUS="조치불필요"; ACTION="자동 업데이트(unattended-upgrades.service)가 이미 활성 상태"
else
    systemctl enable --now unattended-upgrades.service >/tmp/u64_fix.log 2>&1
    FIX_RC=$?
    if [ $FIX_RC -eq 0 ]; then
        STATUS="조치완료"; ACTION="자동 보안 업데이트(unattended-upgrades.service)를 활성화함. 대기 중인 패치는 'apt update && apt upgrade -y' 로 영향도 검토 후 별도 적용 필요"
    else
        STATUS="조치실패"; ACTION="자동 업데이트 서비스 활성화 실패. /tmp/u64_fix.log 확인 필요(관련 패키지 미설치 가능)"
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
