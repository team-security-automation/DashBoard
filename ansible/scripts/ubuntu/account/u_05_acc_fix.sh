#!/bin/bash
CHECK_ID="U-05"
GUIDE="발견된 UID 0 계정의 용도를 운영팀에 확인하세요. 불필요하면 usermod -L [계정명]으로 잠그고, 필요한 계정이면 사유를 기록하세요."

_esc() { printf '%s' "$1" | sed 's|\\|\\\\|g; s|"|\\"|g'; }

printf '{"check_id":"%s","fix_status":"수동조치필요","guide":"%s"}\n' "$(_esc "$CHECK_ID")" "$(_esc "$GUIDE")"
exit 0
