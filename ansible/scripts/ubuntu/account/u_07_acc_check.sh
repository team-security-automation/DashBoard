#!/bin/bash
source "$(dirname "$0")/../../common/json_output.sh"
CHECK_ID="U-07"; CATEGORY="계정관리"; RISK_LEVEL="중"; IS_AUTO_FIXABLE="false"
THRESHOLD_DAYS=90

now_epoch=$(date +%s)
stale=""
while IFS=: read -r username _ uid _ _ _ shell; do
  if [ "$uid" -ge 1000 ] && [ "$shell" != "/usr/sbin/nologin" ] && [ "$shell" != "/bin/false" ]; then
    last_line=$(lastlog -u "$username" 2>/dev/null | tail -1)
    if echo "$last_line" | grep -q "Never logged in"; then
      stale="${stale}${username}(로그인 이력 없음), "
    else
      last_date=$(echo "$last_line" | awk '{print $4,$5,$6,$7}')
      last_epoch=$(date -d "$last_date" +%s 2>/dev/null)
      if [ -n "$last_epoch" ]; then
        diff_days=$(( (now_epoch - last_epoch) / 86400 ))
        if [ "$diff_days" -gt "$THRESHOLD_DAYS" ]; then
          stale="${stale}${username}(마지막 로그인 ${diff_days}일 전), "
        fi
      fi
    fi
  fi
done < /etc/passwd
stale=$(echo "$stale" | sed 's/, $//')

if [ -z "$stale" ]; then
  STATUS="양호"; CURRENT_VALUE="없음"
  EVIDENCE="최근 ${THRESHOLD_DAYS}일 이내에 로그인 기록이 없는 계정이 없습니다. 모든 상시 로그인 가능 계정이 실제로 사용 중임이 확인되어 관리 사각지대가 없습니다."
else
  STATUS="수동확인"; CURRENT_VALUE="$stale"
  EVIDENCE="최근 ${THRESHOLD_DAYS}일 이상 로그인 기록이 없는 계정이 발견되었습니다: ${stale}. 다만 배치 작업이나 서비스 전용 계정일 수 있어, 실제 사용 여부를 부서 담당자가 확인해야 삭제/잠금 여부를 최종 판단할 수 있습니다."
fi
EXPECTED_VALUE="장기 미사용 계정 없음(최근 ${THRESHOLD_DAYS}일 이내 로그인)"

print_json
