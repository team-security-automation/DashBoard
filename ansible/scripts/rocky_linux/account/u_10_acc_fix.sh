#!/bin/bash
CHECK_ID="U-10"
GUIDE="중복된 UID 중 실사용 이력이 적은 계정의 UID를 usermod -u [새UID]로 변경한 후, find / -user [기존UID] -exec chown [새UID] {} \; 로 소유 파일 전체의 소유권을 재조정하세요. 재조정 전 반드시 대상 파일 목록을 먼저 확인하세요."

_esc() { printf '%s' "$1" | sed 's|\\|\\\\|g; s|"|\\"|g'; }

printf '{"check_id":"%s","fix_status":"수동조치필요","guide":"%s"}\n' "$(_esc "$CHECK_ID")" "$(_esc "$GUIDE")"
exit 0
