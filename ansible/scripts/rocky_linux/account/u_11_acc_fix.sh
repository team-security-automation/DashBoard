#!/bin/bash
CHECK_ID="U-11"
BACKUP_PATH="/etc/passwd.bak.$(date +%Y%m%d_%H%M%S)"
FIX_STATUS="실패"
REVERIFIED_STATUS="취약"

cp /etc/passwd "$BACKUP_PATH" 2>/dev/null

if [ -f "$BACKUP_PATH" ]; then
  bad=$(awk -F: '$3<1000 && $1!="root" && ($7=="/bin/bash"||$7=="/bin/sh") {print $1}' /etc/passwd)
  for user in $bad; do
    usermod -s /sbin/nologin "$user" 2>/dev/null
  done

  remaining=$(awk -F: '$3<1000 && $1!="root" && ($7=="/bin/bash"||$7=="/bin/sh") {print $1}' /etc/passwd)
  if [ -z "$remaining" ]; then
    REVERIFIED_STATUS="양호"; FIX_STATUS="성공"
  fi
fi

printf '{"check_id":"%s","fix_status":"%s","backup_path":"%s","reverified_status":"%s"}\n' \
  "$CHECK_ID" "$FIX_STATUS" "$BACKUP_PATH" "$REVERIFIED_STATUS"
[ "$FIX_STATUS" == "성공" ] && exit 0 || exit 1
