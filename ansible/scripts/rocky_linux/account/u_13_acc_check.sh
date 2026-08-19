#!/bin/bash
source "$(dirname "$0")/../../common/json_output.sh"
CHECK_ID="U-13"; CATEGORY="계정관리"; RISK_LEVEL="중"; IS_AUTO_FIXABLE="true"

method=$(grep -E "^\s*ENCRYPT_METHOD" /etc/login.defs 2>/dev/null | awk '{print $2}')

if [ "$method" == "SHA512" ]; then
  STATUS="양호"
  EVIDENCE="/etc/login.defs의 ENCRYPT_METHOD가 SHA512로 설정되어 있어, 신규 생성되는 비밀번호 해시가 충분히 강한 알고리즘으로 저장됩니다."
else
  STATUS="취약"
  EVIDENCE="/etc/login.defs의 ENCRYPT_METHOD가 '${method:-미설정(기본 DES/MD5일 수 있음)}'으로 되어 있습니다. SHA512보다 약한 해시 알고리즘은 연산 속도가 빨라 오프라인 무차별 대입 크래킹에 상대적으로 쉽게 뚫립니다."
fi
CURRENT_VALUE="ENCRYPT_METHOD=${method:-미설정}"
EXPECTED_VALUE="SHA512"

print_json
