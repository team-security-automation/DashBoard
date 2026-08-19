#!/bin/bash
# Manual-review item: 정보 수집용 스크립트
# 정상 실행 시 status는 항상 '수동확인'이며, CURRENT_VALUE/EVIDENCE를 사람이 검토합니다.

CHECK_ID="U-35"
CATEGORY="서비스관리"
EXPECTED_VALUE="공유 서비스의 익명 접근 제한"
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

ISSUES=()
UNKNOWN=()
CHECKED=()

VSFTPD=$(running_units_matching '(^|[-_.@])vsftpd([-_.@]|$)')
PROFTPD=$(running_units_matching '(^|[-_.@])proftpd([-_.@]|$)')
BASIC_FTP=$(running_units_matching '(^|[-_.@])(ftpd|wu-ftpd)([-_.@]|$)')
NFS=$(running_units_matching '(^|[-_.@])(nfs-server|nfs-kernel-server|nfsd)([-_.@]|$)')
SAMBA=$(running_units_matching '(^|[-_.@])(smb|smbd|samba)([-_.@]|$)')

if [ -n "$VSFTPD" ]; then
    CONF=""
    for f in /etc/vsftpd.conf /etc/vsftpd/vsftpd.conf; do
        [ -r "$f" ] && CONF="$f" && break
    done

    if [ -z "$CONF" ]; then
        UNKNOWN+=("vsFTP 활성화 상태이나 설정 파일을 찾지 못함")
    else
        CHECKED+=("vsFTP:$CONF")
        VALUE=$(noncomment_lines "$CONF" | grep -Ei '^[[:space:]]*anonymous_enable[[:space:]]*=' | tail -n 1 || true)

        if printf '%s' "$VALUE" | grep -Eiq '=[[:space:]]*(YES|TRUE|1)([[:space:]]|$)'; then
            ISSUES+=("$CONF:$VALUE")
        elif [ -z "$VALUE" ]; then
            UNKNOWN+=("$CONF anonymous_enable 명시값 없음")
        fi
    fi
fi

if [ -n "$PROFTPD" ]; then
    CONF=""
    for f in /etc/proftpd.conf /etc/proftpd/proftpd.conf; do
        [ -r "$f" ] && CONF="$f" && break
    done

    if [ -z "$CONF" ]; then
        UNKNOWN+=("ProFTP 활성화 상태이나 설정 파일을 찾지 못함")
    else
        CHECKED+=("ProFTP:$CONF")
        if noncomment_lines "$CONF" | grep -Eiq '<Anonymous([[:space:]]|>)|^[[:space:]]*UserAlias[[:space:]]+'; then
            ISSUES+=("$CONF 익명 접근 블록/UserAlias 확인")
        fi
    fi
fi

if [ -n "$BASIC_FTP" ]; then
    CHECKED+=("기본FTP")
    FTP_ACCOUNTS=$(getent passwd ftp anonymous 2>/dev/null || true)
    if [ -n "$FTP_ACCOUNTS" ]; then
        ISSUES+=("기본 FTP 익명 계정 존재: $FTP_ACCOUNTS")
    fi
fi

if [ -n "$NFS" ]; then
    CHECKED+=("NFS:/etc/exports")
    if [ -r /etc/exports ]; then
        NFS_ANON=$(noncomment_lines /etc/exports | grep -Ei 'anonuid|anongid' || true)
        [ -n "$NFS_ANON" ] && ISSUES+=("/etc/exports 익명 매핑 옵션: $NFS_ANON")
    else
        UNKNOWN+=("NFS 활성화 상태이나 /etc/exports를 읽을 수 없음")
    fi
fi

if [ -n "$SAMBA" ]; then
    CHECKED+=("Samba:/etc/samba/smb.conf")
    if [ -r /etc/samba/smb.conf ]; then
        GUEST=$(noncomment_lines /etc/samba/smb.conf | grep -Ei '^[[:space:]]*guest[[:space:]]+ok[[:space:]]*=' || true)
        if printf '%s' "$GUEST" | grep -Eiq '=[[:space:]]*(yes|true|1)([[:space:]]|$)'; then
            ISSUES+=("/etc/samba/smb.conf:$GUEST")
        fi
    else
        UNKNOWN+=("Samba 활성화 상태이나 /etc/samba/smb.conf를 읽을 수 없음")
    fi
fi

if [ -z "$VSFTPD$PROFTPD$BASIC_FTP$NFS$SAMBA" ]; then
    STATUS="양호"
    CURRENT_VALUE="점검 대상 공유 서비스 비활성화"
    EVIDENCE="실행 중인 vsFTP/ProFTP/기본 FTP/NFS/Samba 서비스가 확인되지 않음"
elif [ "${#ISSUES[@]}" -gt 0 ]; then
    STATUS="취약"
    CURRENT_VALUE="익명 접근 허용 설정 확인"
    EVIDENCE="$(printf '%s; ' "${ISSUES[@]}")"
elif [ "${#UNKNOWN[@]}" -gt 0 ]; then
    STATUS="수동확인"
    CURRENT_VALUE="공유 서비스 활성화, 일부 설정 자동 판정 불가"
    EVIDENCE="$(printf '%s; ' "${UNKNOWN[@]}")"
else
    STATUS="양호"
    CURRENT_VALUE="활성 공유 서비스의 익명 접근 제한 확인"
    EVIDENCE="점검 대상=$(printf '%s; ' "${CHECKED[@]}")"
fi

emit_json
exit 0
