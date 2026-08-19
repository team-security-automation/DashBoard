#!/bin/bash
source "$(dirname "$0")/../../common/json_output.sh"
CHECK_ID="U-06"; CATEGORY="계정관리"; RISK_LEVEL="중"; IS_AUTO_FIXABLE="false"

if grep -q "pam_wheel.so" /etc/pam.d/su 2>/dev/null; then
  STATUS="양호"; CURRENT_VALUE="pam_wheel 적용됨"
  EVIDENCE="/etc/pam.d/su에 pam_wheel.so가 적용되어 있어 wheel 그룹 구성원만 su로 root 전환을 시도할 수 있습니다. 일반 계정을 탈취해도 곧바로 su를 시도할 수 없어 공격 경로가 좁아집니다."
else
  STATUS="취약"; CURRENT_VALUE="pam_wheel 미적용"
  EVIDENCE="/etc/pam.d/su에 pam_wheel.so 제한이 설정되어 있지 않습니다. wheel(관리자) 그룹에 속하지 않은 일반 계정도 su 명령으로 root 전환을 시도할 수 있는 상태입니다."
fi
EXPECTED_VALUE="pam_wheel 적용"

print_json
