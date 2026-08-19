#!/bin/bash
# account/file/service/patch/log 하위의 u_XX_*_check.sh를 번호 순으로 모두 실행해
# 결과를 하나의 JSON 배열로 합쳐 stdout으로 출력한다. (계약: ../README.md 참고)
#
# 개별 점검 스크립트 계약:
#   stdout: 진단 성공 시 JSON 객체 1개만 / stderr: 진단 오류 메시지
#   exit 0: 진단 완료(양호/취약 판정과 무관) / exit != 0: 진단 자체 실패 -> 배열에서 제외
set -u
DIR="$(cd "$(dirname "$0")" && pwd)"
ERR_LOG="$DIR/run_all.err"
: > "$ERR_LOG"

results=()
while IFS= read -r -d '' script; do
    output=$(bash "$script" 2>>"$ERR_LOG")
    rc=$?
    if [ "$rc" -eq 0 ] && [ -n "$output" ]; then
        results+=("$output")
    else
        echo "[run_all.sh] $script 실행 실패 (rc=$rc) - 배열에서 제외" >> "$ERR_LOG"
    fi
done < <(find "$DIR" -name '*_check.sh' ! -name "$(basename "$0")" -print0 | sort -z)

{
    printf '['
    for i in "${!results[@]}"; do
        [ "$i" -gt 0 ] && printf ','
        printf '%s' "${results[$i]}"
    done
    printf ']\n'
}
