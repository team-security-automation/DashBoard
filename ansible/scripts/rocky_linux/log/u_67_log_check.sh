#!/bin/bash
# KISA 2026 U-67 - 로그 디렉터리 소유자 및 권한 설정
# Target: Rocky Linux 9/10
# stdout: successful diagnosis JSON only / stderr: diagnosis errors only
# exit 0: diagnosis completed (status=양호/취약), exit != 0: diagnosis error

CHECK_ID="U-67"
CATEGORY="로그 관리"
EXPECTED_VALUE="/var/log 내 로그 파일 root 소유 및 권한 644 이하"
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

[ -d /var/log ] || fail "/var/log 디렉터리가 존재하지 않음"

ISSUES=()
TOTAL=0

while IFS= read -r -d '' f; do
    TOTAL=$((TOTAL + 1))

    OWNER=$(stat -c '%U' "$f" 2>/dev/null) || fail "$f 소유자 확인 실패"
    MODE=$(stat -c '%a' "$f" 2>/dev/null) || fail "$f 권한 확인 실패"

    if [ "$OWNER" != "root" ]; then
        ISSUES+=("$f owner=$OWNER mode=$MODE")
    elif ! perm_within "$MODE" "644"; then
        ISSUES+=("$f owner=$OWNER mode=$MODE")
    fi
done < <(find /var/log -xdev -type f -print0 2>/dev/null)

if [ "${#ISSUES[@]}" -eq 0 ]; then
    STATUS="양호"
    CURRENT_VALUE="/var/log 로그 파일 ${TOTAL}개 기준 충족"
    EVIDENCE="모든 확인 대상 로그 파일의 소유자가 root이고 권한이 644 이하"
else
    STATUS="취약"
    CURRENT_VALUE="/var/log 로그 파일 권한/소유자 기준 미충족 ${#ISSUES[@]}건"
    EVIDENCE="$(printf '%s; ' "${ISSUES[@]:0:20}")"
fi

emit_json
exit 0
