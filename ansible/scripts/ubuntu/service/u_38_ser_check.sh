#!/bin/bash
# KISA 2026 U-38 - DoS 공격에 취약한 서비스 비활성화
# Target: Ubuntu 24/26
# stdout: successful diagnosis JSON only / stderr: diagnosis errors only
# exit 0: diagnosis completed (status=양호/취약), exit != 0: diagnosis error

CHECK_ID="U-38"
CATEGORY="서비스 관리"
EXPECTED_VALUE="echo/discard/daytime/chargen 서비스 비활성화"
RISK_LEVEL="상"
IS_AUTO_FIXABLE=true

json_escape() {
    local s="$1"
    s="${s//\\/\\\\}"
    s="${s//\"/\\\"}"
    s="${s//$'\t'/\\t}"
    s="${s//$'\r'/}"
    s="${s//$'\n'/\\n}"
    printf '%s' "$s"
}

emit_json() {
    local _current_value _evidence
    _current_value=$(json_escape "$CURRENT_VALUE")
    _evidence=$(json_escape "$EVIDENCE")
    cat <<EOF
{
  "check_id": "$CHECK_ID",
  "category": "$CATEGORY",
  "status": "$STATUS",
  "current_value": "$_current_value",
  "expected_value": "$EXPECTED_VALUE",
  "evidence": "$_evidence",
  "hostname": "$(hostname)",
  "risk_level": "$RISK_LEVEL",
  "is_auto_fixable": $IS_AUTO_FIXABLE
}
EOF
}

fail() {
    echo "$CHECK_ID: $*" >&2
    exit 2
}

require_systemctl() {
    command -v systemctl >/dev/null 2>&1 || fail "systemctl 명령을 찾을 수 없음"
}

running_units_matching() {
    local regex="$1"
    systemctl list-units --type=service --state=running --all --no-legend --no-pager 2>/dev/null \
        | awk '{print $1}' \
        | grep -Ei "$regex" || true
}

active_inetd_lines() {
    local regex="$1"
    [ -r /etc/inetd.conf ] || return 0
    grep -Ev '^[[:space:]]*(#|$)' /etc/inetd.conf 2>/dev/null \
        | grep -Ei "$regex" || true
}

active_xinetd_services() {
    local regex="$1"
    local f name result=""

    [ -d /etc/xinetd.d ] || return 0

    for f in /etc/xinetd.d/*; do
        [ -f "$f" ] || continue
        name=$(basename "$f")

        if printf '%s\n' "$name" | grep -Eiq "$regex" || \
           grep -Eiq "service[[:space:]]+.*($regex)" "$f" 2>/dev/null; then
            if grep -Eiq '^[[:space:]]*disable[[:space:]]*=[[:space:]]*no([[:space:]]|$)' "$f" 2>/dev/null; then
                result="${result}${f}"$'\n'
            fi
        fi
    done

    printf '%s' "$result"
}

perm_within() {
    local mode="$1"
    local maximum="$2"

    [[ "$mode" =~ ^[0-7]+$ ]] || return 1
    (( (8#$mode & ~8#$maximum) == 0 ))
}

noncomment_lines() {
    local f="$1"
    [ -r "$f" ] || return 0
    grep -Ev '^[[:space:]]*(#|$)' "$f" 2>/dev/null || true
}

require_systemctl

SYSTEMD=$(running_units_matching '(^|[-_.@])(echo|discard|daytime|chargen)([-_.@]|$)')
INETD=$(active_inetd_lines '(^|[[:space:]])(echo|discard|daytime|chargen)([[:space:]]|$)')
XINETD=$(active_xinetd_services 'echo|discard|daytime|chargen')

if [ -n "$SYSTEMD$INETD$XINETD" ]; then
    STATUS="취약"
    CURRENT_VALUE="DoS 취약 서비스 활성화"
    EVIDENCE="systemd=${SYSTEMD:-없음}; inetd=${INETD:-없음}; xinetd=${XINETD:-없음}"
else
    STATUS="양호"
    CURRENT_VALUE="echo/discard/daytime/chargen 비활성화"
    EVIDENCE="systemd/inetd/xinetd에서 대상 서비스가 확인되지 않음"
fi

emit_json
exit 0
