# 점검 스크립트 개발 가이드 (계정관리/파일/서비스/패치/로그 담당자용)

이 폴더(`ansible/scripts/rocky_linux/`, `ansible/scripts/ubuntu/`)에
각자 개발 중인 `u_XX_acc_check.sh`, `u_XX_file_check.sh`,
`u_XX_ser_check.sh`, `u_XX_pat_check.sh`, `u_XX_log_check.sh`를 넣고,
그걸 순서대로 실행해서 **하나의 JSON 배열**로 합쳐 출력하는
`run_all.sh`를 만들면 대시보드와 바로 연동됩니다.

## run_all.sh가 지켜야 할 것

1. 표준출력(stdout)으로 **JSON 배열 하나만** 출력한다 (배열 앞뒤로 다른 로그 섞으면 파싱 실패).
2. 배열의 각 원소는 아래 필드를 갖는다 (`check_id`, `result`은 필수, 나머지는 선택):

```json
{
  "check_id": "U-01",
  "result": "양호",
  "current_setting": "취약할 때만 채움 (양호면 null 또는 생략)",
  "recommendation": "취약할 때만 채움"
}
```

- `check_id`는 `catalog.py`의 `CheckItem.code`와 **정확히 일치**해야 합니다
  (U-01~U-47, WEB-CI~WEB-WM). 오타나 새 코드가 있으면 대시보드가 매칭 못하고 무시합니다.
- `result`은 `"양호"` / `"취약"` / `"N/A"` 셋 중 하나만 사용합니다.
- `category`, `risk_level`, `os_scope`, `score`는 대시보드가 `check_id`로
  `CheckItem` 테이블을 조회해서 자동으로 채우므로 안 보내도 됩니다.
  (혹시 스크립트에서 자체 판단한 값을 실어 보내고 싶으면 보내도 되고, 그 경우
  대시보드가 그 값을 그대로 신뢰하고 씁니다 — `blueprints/diagnosis.py`의
  `_parse_result_json()` 참고)

## 최소 예시 (개발 중 테스트용)

```bash
#!/bin/bash
# run_all.sh - 임시 예시. 실제로는 u_XX_*_check.sh들을 호출해서 합쳐야 함.
echo '[
  {"check_id": "U-01", "result": "양호"},
  {"check_id": "U-02", "result": "취약", "current_setting": "PASS_MIN_LEN=5", "recommendation": "8자 이상으로 변경"}
]'
```

이 예시만 넣어놔도 대시보드 → 진단 실행이 실제 SSH로 끝까지 동작하는지
파이프라인 테스트는 가능합니다. 실제 점검 로직은 각자 파트 완성되는 대로
`run_all.sh` 안에서 호출하도록 이어붙이면 됩니다.

## 실행 권한

컨트롤 노드에서 대상 서버로 복사된 뒤 `chmod 0700`으로 실행 권한이
자동으로 부여됩니다 (`ansible/playbooks/diagnose.yml`의 `copy` 태스크 참고).
