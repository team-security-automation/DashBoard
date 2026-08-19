#!/bin/bash
# 임시 예시 스크립트 (파이프라인 연결 테스트용).
# 실제로는 u_XX_acc_check.sh / file_check.sh / ser_check.sh / pat_check.sh /
# log_check.sh 를 순서대로 호출해서 그 결과를 하나의 JSON 배열로 합쳐 출력해야 함.
# 자세한 계약은 ../README.md 참고.
echo '[
  {"check_id": "U-01", "result": "양호"},
  {"check_id": "U-02", "result": "취약", "current_setting": "PASS_MIN_LEN=5, pam_pwquality 미적용", "recommendation": "8자 이상 + 복잡도 정책 적용"}
]'
