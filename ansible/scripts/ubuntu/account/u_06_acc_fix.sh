#!/bin/bash
CHECK_ID="U-06"
GUIDE="/etc/pam.d/su에 pam_wheel.so를 추가하세요. 적용 후 wheel 그룹 계정과 일반 계정 각각으로 su 명령어를 테스트하세요."

_esc() { printf '%s' "$1" | sed 's|\\|\\\\|g; s|"|\\"|g'; }

printf '{"check_id":"%s","fix_status":"수동조치필요","guide":"%s"}\n' "$(_esc "$CHECK_ID")" "$(_esc "$GUIDE")"
exit 0
