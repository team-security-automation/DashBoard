#!/bin/bash
# Manual-review item: 정보 수집용 스크립트
# 정상 실행 시 status는 항상 '수동확인'이며, CURRENT_VALUE/EVIDENCE를 사람이 검토합니다.

CHECK_ID="U-47"
CATEGORY="서비스관리"
EXPECTED_VALUE="SMTP 릴레이 제한 또는 릴레이 대상 접근 제어 설정"
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
    STATUS="수동확인"

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

SENDMAIL=$(running_units_matching '(^|[-_.@])sendmail([-_.@]|$)')
POSTFIX=$(running_units_matching '(^|[-_.@])postfix([-_.@]|$)')
EXIM=$(running_units_matching '(^|[-_.@])exim(4)?([-_.@]|$)')

if [ -z "$SENDMAIL$POSTFIX$EXIM" ]; then
    STATUS="양호"
    CURRENT_VALUE="메일 서비스 비활성화"
    EVIDENCE="실행 중인 Sendmail/Postfix/Exim 서비스가 확인되지 않음"
    emit_json
    exit 0
fi

ISSUES=()
UNKNOWN=()
OK=()

if [ -n "$SENDMAIL" ]; then
    BAD=$(grep -Eiv '^[[:space:]]*(dnl|#)' /etc/mail/sendmail.mc 2>/dev/null | grep -Ei 'promiscuous_relay' || true)

    if [ -n "$BAD" ]; then
        ISSUES+=("Sendmail promiscuous_relay 설정 확인: $BAD")
    else
        RELAY_DENIED=$(grep -E '^[^#]*R\$\*' /etc/mail/sendmail.cf 2>/dev/null | grep -Ei 'Relaying denied' || true)
        ACCESS=$(noncomment_lines /etc/mail/access | grep -Ei 'RELAY|REJECT|DISCARD|ERROR' || true)

        if [ -n "$RELAY_DENIED$ACCESS" ]; then
            OK+=("Sendmail 릴레이 제한/접근제어 설정 확인")
        else
            UNKNOWN+=("Sendmail promiscuous_relay는 없으나 명시적 릴레이 제한 근거 추가 확인 필요")
        fi
    fi
fi

if [ -n "$POSTFIX" ]; then
    if [ -r /etc/postfix/main.cf ]; then
        P=$(noncomment_lines /etc/postfix/main.cf | grep -Ei '^[[:space:]]*(smtpd_recipient_restrictions|smtpd_relay_restrictions|mynetworks)[[:space:]]*=' || true)

        if [ -z "$P" ]; then
            ISSUES+=("Postfix 릴레이 관련 설정 미확인")
        elif printf '%s' "$P" | grep -Eiq 'reject_unauth_destination|smtpd_relay_restrictions|mynetworks'; then
            OK+=("Postfix 릴레이 관련 설정: $P")
        else
            UNKNOWN+=("Postfix 릴레이 설정 수동 검토 필요: $P")
        fi
    else
        UNKNOWN+=("Postfix 활성화 상태이나 /etc/postfix/main.cf 읽기 불가")
    fi
fi

if [ -n "$EXIM" ]; then
    CONF=""
    for f in /etc/exim/exim.conf /etc/exim4/exim4.conf /etc/exim4/exim4.conf.template; do
        [ -r "$f" ] && CONF="$f" && break
    done

    if [ -z "$CONF" ]; then
        UNKNOWN+=("Exim 활성화 상태이나 설정 파일을 찾지 못함")
    else
        E=$(noncomment_lines "$CONF" | grep -Ei 'relay_from_hosts|^[[:space:]]*accept[[:space:]]+hosts[[:space:]]*=' || true)

        if [ -n "$E" ]; then
            OK+=("Exim 릴레이 대상 제한 설정: $E")
        else
            ISSUES+=("Exim relay_from_hosts/accept hosts 제한 설정 미확인")
        fi
    fi
fi

if [ "${#ISSUES[@]}" -gt 0 ]; then
    STATUS="취약"
    CURRENT_VALUE="SMTP 릴레이 제한 미흡"
    EVIDENCE="$(printf '%s; ' "${ISSUES[@]}")"
elif [ "${#UNKNOWN[@]}" -gt 0 ]; then
    STATUS="수동확인"
    CURRENT_VALUE="SMTP 릴레이 제한 일부 수동 검토 필요"
    EVIDENCE="$(printf '%s; ' "${UNKNOWN[@]}")"
else
    STATUS="양호"
    CURRENT_VALUE="SMTP 릴레이 제한 설정 확인"
    EVIDENCE="$(printf '%s; ' "${OK[@]}")"
fi

emit_json
exit 0
