#!/bin/bash
CHECK_ID="U-03"
GUIDE="/etc/pam.d/system-auth에 pam_faillock 모듈을 추가하세요. 적용 전 테스트 계정으로 로그인 실패를 반복 시도해 정상적으로 잠기는지, 그리고 정상 계정 로그인이 막히지 않는지 반드시 확인 후 적용하세요."

_esc() { printf '%s' "$1" | sed 's|\\|\\\\|g; s|"|\\"|g'; }

printf '{"check_id":"%s","fix_status":"수동조치필요","guide":"%s"}\n' "$(_esc "$CHECK_ID")" "$(_esc "$GUIDE")"
exit 0
