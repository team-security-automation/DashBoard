#!/bin/bash
# KISA 2026 U-42 - 불필요한 RPC 서비스 비활성화
# Target: Ubuntu 24/26
# stdout: successful diagnosis JSON only / stderr: diagnosis errors only
# exit 0: diagnosis completed (status=양호/취약), exit != 0: diagnosis error

CHECK_ID="U-42"
CATEGORY="서비스 관리"
EXPECTED_VALUE="KISA 지정 불필요 RPC 서비스 비활성화"
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

REGEX='rpc[._-]?cmsd|ttdbserver|sadmind|rusersd|walld|sprayd|rstatd|rpc[._-]?nisd|rexd|pcnfsd|rpc[._-]?statd|rpc[._-]?ypupdated|rquotad|kcms_server|cachefsd'

SYSTEMD=$(running_units_matching "$REGEX")
INETD=$(active_inetd_lines "$REGEX")
XINETD=$(active_xinetd_services "$REGEX")

if [ -n "$SYSTEMD$INETD$XINETD" ]; then
    STATUS="취약"
    CURRENT_VALUE="불필요 RPC 서비스 활성화"
    EVIDENCE="systemd=${SYSTEMD:-없음}; inetd=${INETD:-없음}; xinetd=${XINETD:-없음}"
else
    STATUS="양호"
    CURRENT_VALUE="KISA 지정 불필요 RPC 서비스 비활성화"
    EVIDENCE="rpc.cmsd/rpc.ttdbserverd/sadmind/rusersd/walld/sprayd/rstatd/rpc.nisd/rexd/rpc.pcnfsd/rpc.statd/rpc.ypupdated/rpc.rquotad/kcms_server/cachefsd 활성 항목 없음"
fi

emit_json
exit 0
