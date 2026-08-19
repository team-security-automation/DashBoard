#!/bin/bash
source "$(dirname "$0")/../../common/json_output.sh"
CHECK_ID="U-10"; CATEGORY="계정관리"; RISK_LEVEL="중"; IS_AUTO_FIXABLE="false"

dup=$(awk -F: '{print $3}' /etc/passwd | sort | uniq -d)

if [ -z "$dup" ]; then
  STATUS="양호"; CURRENT_VALUE="중복 없음"
  EVIDENCE="/etc/passwd에서 UID가 중복되는 계정이 없어, 모든 로그·감사 기록에서 행위자를 UID 기준으로 명확히 구분할 수 있습니다."
else
  dup_accounts=$(awk -F: -v dups="$dup" 'BEGIN{n=split(dups,d,"\n")} {for(i=1;i<=n;i++) if($3==d[i]) print $1"(UID:"$3")"}' /etc/passwd | tr '\n' ',' | sed 's/,$//; s/,/, /g')
  STATUS="취약"; CURRENT_VALUE="중복 UID: $dup_accounts"
  EVIDENCE="동일한 UID를 공유하는 계정이 발견되었습니다: ${dup_accounts}. UID가 중복되면 로그·감사 기록에서 실제 행위자를 구분할 수 없어 사고 발생 시 책임 추적(accountability)이 불가능해집니다."
fi
EXPECTED_VALUE="UID 중복 없음"

print_json
