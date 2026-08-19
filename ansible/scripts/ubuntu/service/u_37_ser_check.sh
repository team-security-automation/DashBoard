#!/bin/bash
# KISA 2026 U-37 - crontab 설정파일 권한 설정 미흡
# Target: Ubuntu 24/26
# stdout: successful diagnosis JSON only / stderr: diagnosis errors only
# exit 0: diagnosis completed (status=양호/취약), exit != 0: diagnosis error

CHECK_ID="U-37"
CATEGORY="서비스 관리"
EXPECTED_VALUE="crontab/at 명령 750 이하·SUID 제거, 관련 파일 root 소유 및 640 이하"
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

ISSUES=()
CHECK_COUNT=0

check_command_file() {
    local f="$1"
    [ -e "$f" ] || return 0

    local owner mode
    owner=$(stat -c '%U' "$f" 2>/dev/null) || fail "$f 소유자 확인 실패"
    mode=$(stat -c '%a' "$f" 2>/dev/null) || fail "$f 권한 확인 실패"
    CHECK_COUNT=$((CHECK_COUNT + 1))

    [ "$owner" = "root" ] || ISSUES+=("$f owner=$owner")
    perm_within "$mode" "750" || ISSUES+=("$f mode=$mode (750 이하 필요)")
    (( (8#$mode & 8#4000) == 0 )) || ISSUES+=("$f SUID 설정됨(mode=$mode)")
}

check_related_file() {
    local f="$1"
    [ -f "$f" ] || return 0

    local owner mode
    owner=$(stat -c '%U' "$f" 2>/dev/null) || fail "$f 소유자 확인 실패"
    mode=$(stat -c '%a' "$f" 2>/dev/null) || fail "$f 권한 확인 실패"
    CHECK_COUNT=$((CHECK_COUNT + 1))

    [ "$owner" = "root" ] || ISSUES+=("$f owner=$owner")
    perm_within "$mode" "640" || ISSUES+=("$f mode=$mode (640 이하 필요)")
}

check_command_file /usr/bin/crontab
check_command_file /usr/bin/at

for f in /etc/crontab /etc/cron.allow /etc/cron.deny /etc/at.allow /etc/at.deny; do
    check_related_file "$f"
done

for d in /etc/cron.d /var/spool/cron /var/spool/cron/crontabs /var/spool/at /var/spool/cron/atjobs; do
    [ -d "$d" ] || continue
    while IFS= read -r -d '' f; do
        check_related_file "$f"
    done < <(find "$d" -xdev -type f -print0 2>/dev/null)
done

if [ "${#ISSUES[@]}" -eq 0 ]; then
    STATUS="양호"
    CURRENT_VALUE="cron/at 관련 점검 파일 ${CHECK_COUNT}개 기준 충족"
    EVIDENCE="crontab/at 명령 권한과 SUID, cron/at 관련 파일 root 소유 및 640 이하 여부 확인"
else
    STATUS="취약"
    CURRENT_VALUE="cron/at 권한 기준 미충족 ${#ISSUES[@]}건"
    EVIDENCE="$(printf '%s; ' "${ISSUES[@]:0:20}")"
fi

emit_json
exit 0
