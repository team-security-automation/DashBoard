#!/bin/bash
CHECK_ID="U-02"
CONF="/etc/security/pwquality.conf"
BACKUP_PATH="${CONF}.bak.$(date +%Y%m%d_%H%M%S)"
FIX_STATUS="실패"
REVERIFIED_STATUS="취약"

cp "$CONF" "$BACKUP_PATH" 2>/dev/null

if [ -f "$BACKUP_PATH" ]; then
  if grep -qE "^\s*minlen" "$CONF"; then
    sed -i "s/^\s*minlen.*/minlen = 8/" "$CONF"
  else
    echo "minlen = 8" >> "$CONF"
  fi

  minlen=$(grep -E "^\s*minlen" "$CONF" 2>/dev/null | awk -F= '{print $2}' | tr -d " ")
  if [ -n "$minlen" ] && [ "$minlen" -ge 8 ] 2>/dev/null; then
    REVERIFIED_STATUS="양호"; FIX_STATUS="성공"
  fi
fi

printf '{"check_id":"%s","fix_status":"%s","backup_path":"%s","reverified_status":"%s"}\n' \
  "$CHECK_ID" "$FIX_STATUS" "$BACKUP_PATH" "$REVERIFIED_STATUS"
[ "$FIX_STATUS" == "성공" ] && exit 0 || exit 1

