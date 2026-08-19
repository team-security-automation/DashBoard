#!/bin/bash
# KISA 2026 U-48 - expn, vrfy 명령어 제한
# Target: Rocky Linux 9/10
# stdout: successful diagnosis JSON only / stderr: diagnosis errors only
# exit 0: diagnosis completed (status=양호/취약), exit != 0: diagnosis error

CHECK_ID="U-48"
CATEGORY="서비스 관리"
EXPECTED_VALUE="SMTP expn/vrfy 명령 제한"
RISK_LEVEL="중"
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
    if [ -r /etc/mail/sendmail.cf ]; then
        PRIV=$(noncomment_lines /etc/mail/sendmail.cf | grep -Ei 'PrivacyOptions|^O[[:space:]]*PrivacyOptions' || true)

        if printf '%s' "$PRIV" | grep -Eiq 'goaway'; then
            OK+=("Sendmail goaway")
        elif printf '%s' "$PRIV" | grep -Eiq 'noexpn' && printf '%s' "$PRIV" | grep -Eiq 'novrfy'; then
            OK+=("Sendmail noexpn+novrfy")
        else
            ISSUES+=("Sendmail noexpn/novrfy 또는 goaway 미설정")
        fi
    else
        UNKNOWN+=("Sendmail 활성화 상태이나 /etc/mail/sendmail.cf 읽기 불가")
    fi
fi

if [ -n "$POSTFIX" ]; then
    if [ -r /etc/postfix/main.cf ]; then
        V=$(noncomment_lines /etc/postfix/main.cf | grep -Ei '^[[:space:]]*disable_vrfy_command[[:space:]]*=' | tail -n 1 || true)

        if printf '%s' "$V" | grep -Eiq '=[[:space:]]*yes([[:space:]]|$)'; then
            OK+=("Postfix disable_vrfy_command=yes")
        else
            ISSUES+=("Postfix disable_vrfy_command=yes 미설정")
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
        ALLOW=$(noncomment_lines "$CONF" | grep -Ei '^[[:space:]]*acl_smtp_(vrfy|expn)[[:space:]]*=[[:space:]]*accept' || true)

        if [ -n "$ALLOW" ]; then
            ISSUES+=("Exim expn/vrfy 허용 설정: $ALLOW")
        else
            OK+=("Exim acl_smtp_vrfy/acl_smtp_expn accept 설정 없음")
        fi
    fi
fi

if [ "${#ISSUES[@]}" -gt 0 ]; then
    STATUS="취약"
    CURRENT_VALUE="expn/vrfy 제한 미흡"
    EVIDENCE="$(printf '%s; ' "${ISSUES[@]}")"
elif [ "${#UNKNOWN[@]}" -gt 0 ]; then
    fail "메일 서비스 expn/vrfy 설정 자동 판정 불가: $(printf '%s; ' "${UNKNOWN[@]}")"
else
    STATUS="양호"
    CURRENT_VALUE="expn/vrfy 제한 설정 확인"
    EVIDENCE="$(printf '%s; ' "${OK[@]}")"
fi

emit_json
exit 0
