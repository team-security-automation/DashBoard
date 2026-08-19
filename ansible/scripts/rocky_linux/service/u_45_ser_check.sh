#!/bin/bash
# Manual-review item: 정보 수집용 스크립트
# 정상 실행 시 status는 항상 '수동확인'이며, CURRENT_VALUE/EVIDENCE를 사람이 검토합니다.

CHECK_ID="U-45"
CATEGORY="서비스관리"
EXPECTED_VALUE="메일 서비스 최신 보안 버전 사용"
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

VERSIONS=()

if [ -n "$SENDMAIL" ]; then
    if command -v sendmail >/dev/null 2>&1; then
        V=$(sendmail -d0.1 -bv root 2>/dev/null | head -n 3 | tr '\n' ' ' || true)
        [ -z "$V" ] && V="Sendmail 버전 명령 출력 없음"
        VERSIONS+=("$V")
    else
        fail "Sendmail 서비스 활성화 상태이나 sendmail 명령을 찾을 수 없음"
    fi
fi

if [ -n "$POSTFIX" ]; then
    if command -v postconf >/dev/null 2>&1; then
        V=$(postconf mail_version 2>/dev/null || true)
        [ -z "$V" ] && V="Postfix 버전 명령 출력 없음"
        VERSIONS+=("$V")
    else
        fail "Postfix 서비스 활성화 상태이나 postconf 명령을 찾을 수 없음"
    fi
fi

if [ -n "$EXIM" ]; then
    EXIM_CMD=$(command -v exim || command -v exim4 || true)
    [ -n "$EXIM_CMD" ] || fail "Exim 서비스 활성화 상태이나 exim 명령을 찾을 수 없음"

    V=$("$EXIM_CMD" -bV 2>/dev/null | head -n 2 | tr '\n' ' ' || true)
    [ -z "$V" ] && V="Exim 버전 명령 출력 없음"
    VERSIONS+=("$V")
fi

STATUS="수동확인"
CURRENT_VALUE="메일 서비스 활성화 - 최신 보안 버전 비교 필요"
EVIDENCE="$(printf '%s; ' "${VERSIONS[@]}") 벤더 최신 버전/보안 패치 정보와 비교 필요"

emit_json
exit 0
