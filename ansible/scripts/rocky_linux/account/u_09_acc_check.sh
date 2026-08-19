#!/bin/bash
source "$(dirname "$0")/../../common/json_output.sh"
CHECK_ID="U-09"; CATEGORY="계정관리"; RISK_LEVEL="하"; IS_AUTO_FIXABLE="false"

invalid=""
while IFS=: read -r username _ _ gid _ _ _; do
  getent group "$gid" > /dev/null 2>&1 || invalid="${invalid}${username}(GID:${gid}), "
done < /etc/passwd
invalid=$(echo "$invalid" | sed 's/, $//')

if [ -z "$invalid" ]; then
  STATUS="양호"; CURRENT_VALUE="없음"
  EVIDENCE="/etc/passwd의 모든 계정이 실제 존재하는 그룹(GID)을 참조하고 있어, 계정 생성·삭제 과정에서 발생하는 관리 오류가 없는 상태입니다."
else
  STATUS="취약"; CURRENT_VALUE="$invalid"
  EVIDENCE="/etc/passwd에 존재하지 않는 그룹(GID)을 참조하는 계정이 있습니다: ${invalid}. 이는 계정 생성·삭제 과정에서 발생한 관리 오류의 흔적으로, 파일 소유권이 의도치 않은 GID로 남아 있어 접근 통제에 혼란을 줄 수 있습니다."
fi
EXPECTED_VALUE="모든 GID 유효"

print_json
