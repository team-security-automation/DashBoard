#!/bin/bash
CHECK_ID="U-09"
GUIDE="해당 계정이 원래 속해야 할 그룹을 계정 생성 이력에서 확인한 후 usermod -g [올바른GID] [계정명]으로 재할당하세요."

_esc() { printf '%s' "$1" | sed 's|\\|\\\\|g; s|"|\\"|g'; }

printf '{"check_id":"%s","fix_status":"수동조치필요","guide":"%s"}\n' "$(_esc "$CHECK_ID")" "$(_esc "$GUIDE")"
exit 0
