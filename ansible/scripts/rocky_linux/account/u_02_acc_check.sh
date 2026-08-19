#!/bin/bash
source "$(dirname "$0")/../../common/json_output.sh"
CHECK_ID="U-02"; CATEGORY="계정관리"; RISK_LEVEL="중"; IS_AUTO_FIXABLE="true"

minlen=$(grep -E "^\s*minlen" /etc/security/pwquality.conf 2>/dev/null | awk -F= '{print $2}' | tr -d ' ')

if [ -n "$minlen" ] && [ "$minlen" -ge 8 ] 2>/dev/null; then
  STATUS="양호"
  EVIDENCE="pwquality.conf의 minlen이 ${minlen}로 설정되어 있어 8자 미만의 짧은 비밀번호는 생성할 수 없습니다. 최소 길이 기준을 충족해 무차별 대입 공격에 필요한 시도 경우의 수가 충분히 커집니다."
else
  STATUS="취약"
  EVIDENCE="/etc/security/pwquality.conf의 minlen 값이 '${minlen:-미설정}'입니다. 최소 길이 기준이 없거나 8자 미만이면 짧고 예측 가능한 비밀번호가 허용되어 무차별 대입(brute-force) 및 사전 공격에 취약해집니다."
fi
CURRENT_VALUE="minlen=${minlen:-미설정}"
EXPECTED_VALUE="minlen>=8"

print_json
