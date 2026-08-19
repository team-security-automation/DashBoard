#!/bin/bash
CHECK_ID="U-04"
BACKUP_PATH="/etc/shadow.bak.$(date +%Y%m%d_%H%M%S)"
FIX_STATUS="실패"
REVERIFIED_STATUS="취약"

cp -p /etc/shadow "$BACKUP_PATH" 2>/dev/null

if [ -f "$BACKUP_PATH" ]; then
  chmod 400 /etc/shadow

  perm=$(stat -c "%a" /etc/shadow 2>/dev/null)
  if [ -n "$perm" ] && [ "$perm" -le 400 ] 2>/dev/null; then
    REVERIFIED_STATUS="양호"; FIX_STATUS="성공"
  fi
fi

printf '{"check_id":"%s","fix_status":"%s","backup_path":"%s","reverified_status":"%s"}\n' \
  "$CHECK_ID" "$FIX_STATUS" "$BACKUP_PATH" "$REVERIFIED_STATUS"
[ "$FIX_STATUS" == "성공" ] && exit 0 || exit 1

