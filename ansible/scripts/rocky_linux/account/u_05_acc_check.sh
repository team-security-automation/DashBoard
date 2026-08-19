#!/bin/bash
source "$(dirname "$0")/../../common/json_output.sh"
CHECK_ID="U-05"; CATEGORY="계정관리"; RISK_LEVEL="상"; IS_AUTO_FIXABLE="false"

extra_root=$(awk -F: '$3==0 && $1!="root" {print $1}' /etc/passwd | tr '\n' ',' | sed 's/,$//; s/,/, /g')

if [ -z "$extra_root" ]; then
  STATUS="양호"; CURRENT_VALUE="없음"
  EVIDENCE="/etc/passwd에 root 외 UID 0을 가진 계정이 없습니다. 최고 권한 계정이 root 하나로 유지되고 있어 은닉 관리자 계정을 통한 백도어 위험이 없습니다."
else
  STATUS="수동확인"; CURRENT_VALUE="$extra_root"
  EVIDENCE="/etc/passwd에서 root 외에 UID 0을 가진 계정이 발견되었습니다: ${extra_root}. UID 0은 root와 동일한 최고 권한을 의미하므로 은닉 백도어 계정일 수 있으나, 정당한 용도(특수 서비스 계정 등)로 생성됐을 가능성도 있어 담당자의 용도 확인이 필요합니다."
fi
EXPECTED_VALUE="root만 UID 0"

print_json
