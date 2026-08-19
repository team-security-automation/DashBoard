#!/bin/bash
# Manual-review item: 정보 수집용 스크립트
# 정상 실행 시 status는 항상 '수동확인'이며, CURRENT_VALUE/EVIDENCE를 사람이 검토합니다.

CHECK_ID="U-39"
CATEGORY="서비스관리"
EXPECTED_VALUE="불필요한 NFS 서비스 비활성화"
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

NFS=$(running_units_matching '(^|[-_.@])(nfs-server|nfs-kernel-server|nfsd|nfs)([-_.@]|$)')

if [ -z "$NFS" ]; then
    STATUS="양호"
    CURRENT_VALUE="NFS 서비스 비활성화"
    EVIDENCE="실행 중인 NFS 관련 서비스가 확인되지 않음"
else
    STATUS="수동확인"
    CURRENT_VALUE="NFS 서비스 활성화"
    EVIDENCE="활성 서비스=${NFS}; KISA 항목은 '불필요한' NFS 사용 여부를 판단하므로 실제 업무상 필요 여부 확인 필요"
fi

emit_json
exit 0
