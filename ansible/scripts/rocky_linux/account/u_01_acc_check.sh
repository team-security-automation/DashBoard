#!/bin/bash
source "$(dirname "$0")/../../common/json_output.sh"
CHECK_ID="U-01"; CATEGORY="계정관리"; RISK_LEVEL="상"; IS_AUTO_FIXABLE="true"

value=$(grep -E "^\s*PermitRootLogin" /etc/ssh/sshd_config 2>/dev/null | awk '{print $2}' | tail -1)

if [ "$value" == "no" ]; then
  STATUS="양호"
  EVIDENCE="PermitRootLogin이 no로 설정되어 있어 root 계정으로는 SSH 원격 로그인이 차단됩니다. 공격자가 root 비밀번호를 알아내도 SSH로 직접 로그인할 수 없어 관리자 권한 직접 탈취 경로가 막혀 있습니다."
else
  STATUS="취약"
  EVIDENCE="PermitRootLogin이 '${value:-미설정(기본값 적용)}'로 되어 있어 root 계정으로 SSH 원격 로그인이 허용됩니다. 공격자가 root 비밀번호나 키만 확보하면 별도의 권한 상승 없이 곧바로 최고 관리자 권한을 획득할 수 있습니다."
fi
CURRENT_VALUE="PermitRootLogin ${value:-미설정}"
EXPECTED_VALUE="PermitRootLogin no"

print_json
