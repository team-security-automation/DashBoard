#!/bin/bash
source "$(dirname "$0")/../../common/json_output.sh"
CHECK_ID="U-11"; CATEGORY="계정관리"; RISK_LEVEL="하"; IS_AUTO_FIXABLE="true"

bad=$(awk -F: '$3<1000 && $1!="root" && ($7=="/bin/bash"||$7=="/bin/sh") {print $1}' /etc/passwd | tr '\n' ',' | sed 's/,$//; s/,/, /g')

if [ -z "$bad" ]; then
  STATUS="양호"; CURRENT_VALUE="없음"
  EVIDENCE="UID 1000 미만의 시스템(서비스) 계정 중 로그인 쉘이 부여된 계정이 없습니다. 시스템 계정이 nologin으로 유지되어 있어 탈취 시 로그인 경로로 악용될 여지가 없습니다."
else
  STATUS="취약"; CURRENT_VALUE="$bad"
  EVIDENCE="UID 1000 미만의 시스템(서비스) 계정인데도 로그인 쉘이 부여된 계정이 있습니다: ${bad}. 시스템 계정은 사람이 직접 로그인할 필요가 없는데 쉘이 살아있으면, 그 계정이 탈취될 경우 공격자의 로그인 경로로 악용됩니다."
fi
EXPECTED_VALUE="시스템계정은 nologin"

print_json
