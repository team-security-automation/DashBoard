#!/bin/bash
CHECK_ID="U-07"
GUIDE="발견된 계정의 실사용 여부를 부서 담당자에게 확인하세요. 미사용이 확정되면 usermod -L [계정명]으로 먼저 잠그고, 일정 기간 후 삭제를 검토하세요."

_esc() { printf '%s' "$1" | sed 's|\\|\\\\|g; s|"|\\"|g'; }

printf '{"check_id":"%s","fix_status":"수동조치필요","guide":"%s"}\n' "$(_esc "$CHECK_ID")" "$(_esc "$GUIDE")"
exit 0
