#!/bin/bash
CHECK_ID="U-01"
CONF="/etc/ssh/sshd_config"
BACKUP_PATH="${CONF}.bak.$(date +%Y%m%d_%H%M%S)"
FIX_STATUS="실패"
REVERIFIED_STATUS="취약"

cp "$CONF" "$BACKUP_PATH" 2>/dev/null

if [ -f "$BACKUP_PATH" ]; then
  if grep -qE "^\s*PermitRootLogin" "$CONF"; then
    sed -i 's/^\s*PermitRootLogin.*/PermitRootLogin no/' "$CONF"
  else
    echo "PermitRootLogin no" >> "$CONF"
  fi
  systemctl restart ssh 2>/dev/null

  value=$(grep -E "^\s*PermitRootLogin" "$CONF" 2>/dev/null | awk '{print $2}' | tail -1)
  if [ "$value" == "no" ]; then
    REVERIFIED_STATUS="양호"; FIX_STATUS="성공"
  fi
fi

printf '{"check_id":"%s","fix_status":"%s","backup_path":"%s","reverified_status":"%s"}\n' \
  "$CHECK_ID" "$FIX_STATUS" "$BACKUP_PATH" "$REVERIFIED_STATUS"
[ "$FIX_STATUS" == "성공" ] && exit 0 || exit 1
