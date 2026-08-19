#!/bin/bash
# KISA 2026 U-36 - r 계열 서비스 비활성화
# Target: Rocky Linux 9/10
# stdout: successful diagnosis JSON only / stderr: diagnosis errors only
# exit 0: diagnosis completed (status=양호/취약), exit != 0: diagnosis error

CHECK_ID="U-36"
CATEGORY="서비스 관리"
EXPECTED_VALUE="rlogin/rsh/rexec 서비스 비활성화"
RISK_LEVEL="상"
IS_AUTO_FIXABLE=false

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

SYSTEMD=$(running_units_matching '(^|[-_.@])(rlogin|rsh|rexec)([-_.@]|$)')
INETD=$(active_inetd_lines '(^|[[:space:]])(rlogin|rsh|rexec|login|shell|exec)([[:space:]]|$)')
XINETD=$(active_xinetd_services 'rlogin|rsh|rexec')

ACTIVE="${SYSTEMD}${INETD}${XINETD}"

if [ -z "$ACTIVE" ]; then
    STATUS="양호"
    CURRENT_VALUE="r 계열 서비스 비활성화"
    EVIDENCE="systemd/inetd/xinetd에서 rlogin/rsh/rexec 활성 항목이 확인되지 않음"
else
    USE_EVIDENCE=""

    if [ -r /etc/hosts.equiv ]; then
        H=$(noncomment_lines /etc/hosts.equiv)
        [ -n "$H" ] && USE_EVIDENCE="/etc/hosts.equiv 설정 존재"
    fi

    RHOSTS=$(find /root /home -maxdepth 2 -type f -name .rhosts -size +0c 2>/dev/null | head -n 10 || true)
    [ -n "$RHOSTS" ] && USE_EVIDENCE="${USE_EVIDENCE}; .rhosts=${RHOSTS}"

    if [ -n "$USE_EVIDENCE" ]; then
        STATUS="양호"
        CURRENT_VALUE="r 계열 서비스 활성화(사용 설정 확인)"
        EVIDENCE="활성 서비스=${ACTIVE}; KISA 가이드의 사용 여부 확인 근거=${USE_EVIDENCE}"
    else
        STATUS="취약"
        CURRENT_VALUE="불필요한 r 계열 서비스 활성화"
        EVIDENCE="활성 서비스=${ACTIVE}; /etc/hosts.equiv 또는 .rhosts에서 사용 설정을 확인하지 못함"
    fi
fi

emit_json
exit 0
