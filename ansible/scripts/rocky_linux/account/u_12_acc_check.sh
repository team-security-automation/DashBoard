#!/bin/bash
source "$(dirname "$0")/../../common/json_output.sh"
CHECK_ID="U-12"; CATEGORY="계정관리"; RISK_LEVEL="하"; IS_AUTO_FIXABLE="true"

tmout=$(grep -E "^\s*TMOUT=" /etc/profile 2>/dev/null | tail -1 | awk -F= '{print $2}' | tr -d '; ')

if [ -n "$tmout" ] && [ "$tmout" -le 600 ] 2>/dev/null; then
  STATUS="양호"
  EVIDENCE="/etc/profile에 TMOUT=${tmout}로 설정되어 있어, 사용자가 터미널을 10분 이상 방치하면 세션이 자동으로 종료됩니다. 물리적 접근을 통한 무단 사용 위험이 줄어듭니다."
else
  STATUS="취약"
  EVIDENCE="/etc/profile에 세션 자동 종료(TMOUT) 값이 '${tmout:-미설정}'으로 되어 있습니다. 값이 없거나 600초(10분)를 초과하면, 사용자가 로그인한 터미널을 방치했을 때 세션이 오래 열려 있어 물리적 접근을 통한 무단 사용에 노출됩니다."
fi
CURRENT_VALUE="TMOUT=${tmout:-미설정}"
EXPECTED_VALUE="TMOUT<=600"

print_json
