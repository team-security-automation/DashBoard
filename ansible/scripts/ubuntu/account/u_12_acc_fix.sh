#!/bin/bash
CHECK_ID="U-12"
CONF="/etc/profile"
BACKUP_PATH="${CONF}.bak.$(date +%Y%m%d_%H%M%S)"
FIX_STATUS="실패"
REVERIFIED_STATUS="취약"

cp "$CONF" "$BACKUP_PATH" 2>/dev/null

if [ -f "$BACKUP_PATH" ]; then
  if grep -qE "^\s*TMOUT=" "$CONF"; then
    sed -i 's/^\s*TMOUT=.*/TMOUT=600/' "$CONF"
  else
    { echo "TMOUT=600"; echo "readonly TMOUT"; echo "export TMOUT"; } >> "$CONF"
  fi

  tmout=$(grep -E "^\s*TMOUT=" "$CONF" 2>/dev/null | tail -1 | awk -F= '{print $2}' | tr -d '; ')
  if [ -n "$tmout" ] && [ "$tmout" -le 600 ] 2>/dev/null; then
    REVERIFIED_STATUS="양호"; FIX_STATUS="성공"
  fi
fi

printf '{"check_id":"%s","fix_status":"%s","backup_path":"%s","reverified_status":"%s"}\n' \
  "$CHECK_ID" "$FIX_STATUS" "$BACKUP_PATH" "$REVERIFIED_STATUS"
[ "$FIX_STATUS" == "성공" ] && exit 0 || exit 1
