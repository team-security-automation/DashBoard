# 점검 스크립트 개발 가이드 (계정관리/파일/서비스/패치/로그 담당자용)

이 폴더(`ansible/scripts/rocky_linux/`, `ansible/scripts/ubuntu/`)에
각자 개발 중인 `u_XX_acc_check.sh`, `u_XX_file_check.sh`,
`u_XX_ser_check.sh`, `u_XX_pat_check.sh`, `u_XX_log_check.sh`를 넣고,
그걸 순서대로 실행해서 **하나의 JSON 배열**로 합쳐 출력하는
`run_all.sh`를 만들면 대시보드와 바로 연동됩니다.

## run_all.sh가 지켜야 할 것

1. 표준출력(stdout)으로 **JSON 배열 하나만** 출력한다 (배열 앞뒤로 다른 로그 섞으면 파싱 실패).
2. 배열의 각 원소(개별 점검 스크립트가 출력하는 JSON 객체 하나)는 아래 필드를 갖는다.
   `check_id`, `status`는 **항상** 채우고, 나머지는 **취약일 때만** 채운다 (양호면 생략 또는 빈 문자열):

```json
{
  "check_id": "U-01",
  "category": "계정 관리",
  "status": "취약",
  "current_value": "PermitRootLogin이 yes로 설정됨",
  "expected_value": "PermitRootLogin을 no로 설정",
  "evidence": "sshd_config 46번째 줄에서 PermitRootLogin yes 확인",
  "hostname": "rocky01",
  "risk_level": "상",
  "is_auto_fixable": true
}
```

- `check_id`는 `catalog.py`의 `CheckItem.code`와 **정확히 일치**해야 합니다
  (U-01~U-47, WEB-CI~WEB-WM). 오타나 새 코드가 있으면 대시보드가 매칭 못하고 무시합니다.
- `status`는 `"양호"` / `"취약"` / `"N/A"` 셋 중 하나만 사용합니다.
- `current_value` → 대시보드의 "현재 설정"으로 저장됩니다.
- `expected_value` → 대시보드의 "조치 권고"로 저장됩니다 (승인 화면에 "이렇게 바뀝니다"로 표시).
- `evidence` → 판정 근거로 별도 저장됩니다 (참고용, 현재 화면에는 노출 안 함).
- `category`, `risk_level`, `os_scope`, `hostname`은 **대시보드가 실제로 읽지 않습니다.**
  `check_id`로 `catalog.py`를 조회해서 category/risk_level/os_scope를 자동으로 채우고,
  대상 서버는 결과 파일명(`<hostname>.json`)으로 이미 식별하기 때문입니다. 스크립트
  내부 로직에서 쓰는 건 상관없지만, JSON 출력에 넣어도 대시보드 동작에는 영향 없습니다.
- `is_auto_fixable`은 `true` / `false` boolean입니다 (선택 필드).
  담당자가 직접 눈으로 확인해야만 조치 가능한 항목(예: 코드 수정, 조직적 정책
  변경이 필요한 항목)은 `false`로 보내주세요. **`false`로 표시된 항목은
  승인자가 승인해도 대시보드가 자동으로 조치를 실행하지 않고, 실무자가 직접
  조치한 뒤 "수동 조치 완료 처리" 버튼을 눌러야 완료 처리됩니다.**
  안 보내면 `impact.py`의 `CHECK_IMPACT_MAP` 기준 기본값(코드 배포·재부팅이
  필요한 항목만 수동, 나머지는 자동)이 대신 적용됩니다.
- (구버전 호환) `result`/`current_setting`/`recommendation`/`remediation_type`
  필드명으로 보내도 여전히 인식됩니다 — `blueprints/diagnosis.py`의
  `_parse_result_json()` 참고. 새로 짜는 스크립트는 위 표기
  (`status`/`current_value`/`expected_value`/`is_auto_fixable`)를 쓰면 됩니다.

## 최소 예시 (개발 중 테스트용)

```bash
#!/bin/bash
# run_all.sh - 임시 예시. 실제로는 u_XX_*_check.sh들을 호출해서 합쳐야 함.
echo '[
  {"check_id": "U-01", "status": "양호"},
  {"check_id": "U-02", "status": "취약", "current_value": "PASS_MIN_LEN=5", "expected_value": "8자 이상으로 변경", "remediation_type": "auto"}
]'
```

이 예시만 넣어놔도 대시보드 → 진단 실행이 실제 SSH로 끝까지 동작하는지
파이프라인 테스트는 가능합니다. 실제 점검 로직은 각자 파트 완성되는 대로
`run_all.sh` 안에서 호출하도록 이어붙이면 됩니다.

## 실행 권한

컨트롤 노드에서 대상 서버로 복사된 뒤 `chmod 0700`으로 실행 권한이
자동으로 부여됩니다 (`ansible/playbooks/diagnose.yml`의 `copy` 태스크 참고).
