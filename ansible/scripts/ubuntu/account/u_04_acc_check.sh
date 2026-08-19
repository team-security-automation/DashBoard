#!/bin/bash
source "$(dirname "$0")/../../common/json_output.sh"
CHECK_ID="U-04"; CATEGORY="계정관리"; RISK_LEVEL="상"; IS_AUTO_FIXABLE="true"

perm=$(stat -c "%a" /etc/shadow 2>/dev/null)

if [ -n "$perm" ] && [ "$perm" -le 400 ] 2>/dev/null; then
  STATUS="양호"
  EVIDENCE="/etc/shadow 권한이 ${perm}로 root(소유자)만 읽을 수 있게 제한되어 있어, 일반 계정은 비밀번호 해시에 접근할 수 없습니다."
else
  STATUS="취약"
  EVIDENCE="/etc/shadow 파일의 권한이 '${perm:-확인불가}'로 설정되어 있어 root 외 계정도 비밀번호 해시를 열람할 수 있는 상태입니다. 해시가 유출되면 오프라인 크래킹 공격에 악용될 수 있습니다."
fi
CURRENT_VALUE="/etc/shadow 권한:${perm:-확인불가}"
EXPECTED_VALUE="400 이하"

print_json
