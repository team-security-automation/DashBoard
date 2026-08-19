#!/bin/bash
# KISA 2026 U-65 - NTP 및 시각 동기화 설정
# Target: Ubuntu 24/26
# stdout: successful diagnosis JSON only / stderr: diagnosis errors only
# exit 0: diagnosis completed (status=양호/취약), exit != 0: diagnosis error

CHECK_ID="U-65"
CATEGORY="로그 관리"
EXPECTED_VALUE="NTP/Chrony 등 시각 동기화 설정 및 실제 동기화 상태 확인"
RISK_LEVEL="중"
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

NTP_UNITS=$(running_units_matching '(^|[-_.@])(ntp|ntpd)([-_.@]|$)')
CHRONY_UNITS=$(running_units_matching '(^|[-_.@])(chrony|chronyd)([-_.@]|$)')
TIMESYNCD=$(running_units_matching '(^|[-_.@])systemd-timesyncd([-_.@]|$)')

SYNC_OK=0
EVIDENCE_PARTS=()

if [ -n "$CHRONY_UNITS" ] && command -v chronyc >/dev/null 2>&1; then
    TRACK=$(chronyc tracking 2>/dev/null || true)
    SOURCES=$(chronyc sources 2>/dev/null | head -n 12 || true)

    if printf '%s\n' "$TRACK" | grep -Eiq 'Leap status[[:space:]]*:[[:space:]]*Normal'; then
        SYNC_OK=1
    fi

    EVIDENCE_PARTS+=("chrony_units=$CHRONY_UNITS; tracking=$(printf '%s' "$TRACK" | head -n 8); sources=$SOURCES")
fi

if [ -n "$NTP_UNITS" ] && command -v ntpq >/dev/null 2>&1; then
    PEERS=$(ntpq -pn 2>/dev/null || true)

    if printf '%s\n' "$PEERS" | grep -Eq '^\*'; then
        SYNC_OK=1
    fi

    EVIDENCE_PARTS+=("ntp_units=$NTP_UNITS; peers=$(printf '%s' "$PEERS" | head -n 12)")
fi

if [ -n "$TIMESYNCD" ] && command -v timedatectl >/dev/null 2>&1; then
    TS=$(timedatectl show -p NTPSynchronized --value 2>/dev/null || true)
    [ "$TS" = "yes" ] && SYNC_OK=1
    EVIDENCE_PARTS+=("systemd-timesyncd=$TIMESYNCD; NTPSynchronized=$TS")
fi

if [ "$SYNC_OK" -eq 1 ]; then
    STATUS="양호"
    CURRENT_VALUE="시각 동기화 정상"
    EVIDENCE="$(printf '%s; ' "${EVIDENCE_PARTS[@]}")"
elif [ -z "$NTP_UNITS$CHRONY_UNITS$TIMESYNCD" ]; then
    STATUS="취약"
    CURRENT_VALUE="NTP/Chrony/시간 동기화 서비스 비활성화"
    EVIDENCE="실행 중인 ntp/ntpd/chrony/chronyd/systemd-timesyncd 서비스가 확인되지 않음"
else
    STATUS="취약"
    CURRENT_VALUE="시간 동기화 서비스는 활성화되어 있으나 동기화 상태 미확인"
    EVIDENCE="$(printf '%s; ' "${EVIDENCE_PARTS[@]}")"
fi

emit_json
exit 0
