#!/bin/bash
source "$(dirname "$0")/../../common/json_output.sh"
CHECK_ID="U-03"; CATEGORY="계정관리"; RISK_LEVEL="상"; IS_AUTO_FIXABLE="false"

if grep -q "pam_faillock" /etc/pam.d/common-auth 2>/dev/null; then
  STATUS="양호"; CURRENT_VALUE="pam_faillock 적용됨"
  EVIDENCE="/etc/pam.d/common-auth에 pam_faillock 모듈이 적용되어 있어, 반복된 로그인 실패 시 계정이 일정 시간 잠깁니다. 이를 통해 공격자의 무제한 비밀번호 대입 시도를 차단합니다."
else
  STATUS="취약"; CURRENT_VALUE="pam_faillock 미적용"
  EVIDENCE="/etc/pam.d/common-auth에 pam_faillock 모듈이 설정되어 있지 않습니다. 로그인 실패 횟수를 제한하는 정책이 없어 공격자가 비밀번호를 무제한으로 시도(brute-force)할 수 있습니다."
fi
EXPECTED_VALUE="pam_faillock 적용"

print_json
