#!/bin/bash
CHECK_ID="U-08"
GUIDE="관리자 그룹 구성원 중 실제 업무상 권한이 필요 없는 인원을 팀 협의로 확정한 후 gpasswd -d [계정명] sudo로 제외하세요."

_esc() { printf '%s' "$1" | sed 's|\\|\\\\|g; s|"|\\"|g'; }

printf '{"check_id":"%s","fix_status":"수동조치필요","guide":"%s"}\n' "$(_esc "$CHECK_ID")" "$(_esc "$GUIDE")"
exit 0
