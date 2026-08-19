#!/bin/bash
# print_json() : 인자를 받지 않고 아래 전역변수를 읽어 scan.yaml이 기대하는 필드로 JSON을 출력한다.
#   CHECK_ID, CATEGORY, STATUS, CURRENT_VALUE, EXPECTED_VALUE, EVIDENCE, RISK_LEVEL, IS_AUTO_FIXABLE
# IS_AUTO_FIXABLE 은 문자열 "true"/"false"를 받아 따옴표 없는 JSON boolean으로 출력한다.
# hostname/os_type/timestamp는 여기서 채우지 않는다 (Ansible gather_facts가 별도 처리).
print_json() {
  local bool="false"
  [ "$IS_AUTO_FIXABLE" == "true" ] && bool="true"

  _esc() { printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'; }

  printf '{"check_id":"%s","category":"%s","status":"%s","current_value":"%s","expected_value":"%s","evidence":"%s","risk_level":"%s","is_auto_fixable":%s}\n' \
    "$(_esc "$CHECK_ID")" "$(_esc "$CATEGORY")" "$(_esc "$STATUS")" "$(_esc "$CURRENT_VALUE")" \
    "$(_esc "$EXPECTED_VALUE")" "$(_esc "$EVIDENCE")" "$(_esc "$RISK_LEVEL")" "$bool"
}
