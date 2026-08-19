# KISA U-01~U-67 다중 서버 보안 자동화 플랫폼 — 대시보드

3팀 착수보고서(2026.08.18) 기준으로 구축한 **웹 대시보드 프로토타입**입니다.
Flask + flask-login + Chart.js + SQLAlchemy(데모: SQLite, 운영: MySQL 전환 가능)로 만들었고,
착수보고서에 명시된 6대 핵심 기능과 `claude_차별화_아이디어.md`의 대시보드 차별화 아이디어를
모두 반영해 실제로 클릭·조작 가능한 상태로 구현했습니다.

## 왜 이렇게 만들었나

- **점수 산출식**: 프로젝트에 첨부된 "등급계산참고_취약점 분석·평가 점수 산출식 예시" 원문 그대로
  구현했습니다 (`scoring.py`). 위험도 상/중/하 배점(10/8/6), 보안수준 = [(전체 − 식별) / 전체] × 100,
  91↑ 우수 / 81~90 양호 / 71~80 보통 / 61~70 미흡 / 60↓ 취약 등급 구간까지 그대로입니다.
- **점검항목 카탈로그**: 프로젝트에 첨부된 KISA 상세가이드 원문에서 Unix 계정관리(U-01~13)·
  파일및디렉터리관리(U-14~33)·서비스관리(U-34~41) 항목명·위험도를 그대로 옮겼습니다.
  U-42~47(서비스관리 일부·패치관리·로그관리)과 Web 21항목(CI/SI/XS 등)은 `catalog.py` 상단
  주석에 출처와 구성 근거를 남겼습니다 — 실제 스크립트 개발 단계에서 가이드 원문으로 교체하면 됩니다.
- **JSON 스키마**: WBS에 적힌 "check_id~recommendation 등 11개 필드" 요구사항을 그대로
  `ScanResult.to_dict()`에 구현했습니다. Ansible이 회수하는 JSON을 이 11개 필드 형태로만
  맞추면 그대로 이 DB에 적재됩니다.
- **디자인**: 관제실(control room) 톤의 다크 콘솔 UI. 착수보고서의 색상 규칙(양호=초록,
  취약=빨강, 수동확인=노랑)을 그대로 브랜드 컬러로 사용했고, 차별화 문서의 원칙대로
  무지개색을 쓰지 않았습니다.

## 6대 핵심 기능 구현 현황

| 기능 | 구현 내용 |
|---|---|
| 서버 관리 | 개별 등록/CSV 일괄 등록/수정/삭제 (`/servers`) |
| 진단 실행 | 전체·개별 실행, 진행률 실시간 표시 (`/diagnosis`, 백그라운드 스레드 + 폴링 API) |
| 결과 시각화 | 보안점수·카테고리별 분포, 검색·필터·정렬 가능한 항목별 상세 (`/servers/<id>`) |
| 조치 승인 | 미리보기(dry-run) → 승인요청 → 승인/거부 → 자동 실행 → 전후비교 (`/approvals`) |
| 이력 관리 | 서버별/전체 시계열 추세, 조치 이력 (`/history`) |
| 권한 관리 | 관리자(실무자)/승인자/일반(조회) 3단계, flask-login 기반 |

### 차별화 아이디어 반영

- **서버 × 점검항목 히트맵 매트릭스** — 대시보드 상단, 5서버 × 68항목(webdb는 Unix47+Web21)을
  한 화면에서 색상으로 표시. 셀 클릭 시 해당 서버 상세로 drill-down.
- **위험도 기반 조치 우선순위 큐** — "배점 × 영향받는 서버 수"로 정렬한 Top 10.
- **KPI 스탯 카드 + 트렌드** — 평균 보안점수·주간 변화율·Critical 미조치 건수·승인대기 건수.
- **컴플라이언스 준수율 뷰** — 카테고리별 준수율 바 차트.
- **조치 전/후 비교** — 승인 상세 페이지에서 서버 보안점수 변화를 숫자로 비교.

## 실행 방법

```bash
cd dashboard
pip install -r requirements.txt --break-system-packages   # 또는 venv 사용 권장
python app.py
```

브라우저에서 http://localhost:5050 접속. **최초 실행 시 자동으로 데모 데이터가 시드**됩니다
(`security_automation.db` 파일이 없으면 자동 생성). 다시 시드하려면 그 파일을 지우고 재실행하거나
`python seed_data.py`를 직접 실행하세요.

### 데모 계정

| 아이디 | 비밀번호 | 권한 |
|---|---|---|
| admin | admin123! | 실무자(관리자) — 서버 관리, 진단 실행, 승인 요청 |
| approver | approve123! | 승인자 — 조치 승인/거부 |
| viewer | viewer123! | 일반 — 조회만 |

### 데모 서버 구성 (착수보고서 인프라 그대로)

| 호스트 | OS | 역할 |
|---|---|---|
| rocky01 | Rocky Linux 9 | WAS |
| rocky02 | Rocky Linux 10 | 배치 서버 |
| ubuntu01 | Ubuntu 24.04 | 파일 서버 |
| ubuntu02 | Ubuntu 26.04 | 모니터링 서버 |
| webdb01 | Rocky Linux 9 | 웹서버+DB (Unix 47항목 + Web 21항목) |

## MySQL로 전환하기

`config.py`의 `SQLALCHEMY_DATABASE_URI` 한 줄만 바꾸면 됩니다.

```python
SQLALCHEMY_DATABASE_URI = "mysql+pymysql://user:password@127.0.0.1:3306/security_automation?charset=utf8mb4"
```

`pip install pymysql --break-system-packages` 필요. 나머지 코드는 SQLAlchemy ORM으로
작성되어 있어 그대로 동작합니다.

## 실제 SSH 진단으로 전환하기

이제 시뮬레이션과 실제 Ansible 실행이 **둘 다 코드에 있고, 설정 한 줄로 전환**됩니다.

```bash
# .env 또는 실행 전 환경변수로
export USE_REAL_ANSIBLE=true
```

또는 `config.py`의 `USE_REAL_ANSIBLE = os.environ.get(...)` 줄을 직접 `True`로 바꿔도 됩니다.

### 전환 전 준비해야 할 것

1. **컨트롤 노드에 Ansible 설치** — `pip install -r requirements.txt`에 `ansible-core`,
   `ansible-runner`를 넣어뒀지만, 배포 환경에 따라 `apt install ansible` 이 더 안정적일 수 있습니다.
2. **서버별 SSH 키 배포** — 대상 서버 5대에 컨트롤 노드의 공개키를 미리 등록해두고
   (`ssh-copy-id` 등), 개인키 파일을 컨트롤 노드에 둡니다. **권한은 반드시 600.**
   ```bash
   chmod 600 /etc/ansible/keys/*.pem
   ```
3. **대시보드에서 서버별 SSH 정보 입력** — 서버 관리 → 서버 수정에서
   SSH 계정 / 포트 / 개인키 경로를 채웁니다. 안 채운 서버는 인벤토리에서
   자동으로 빠지고, 진단 화면에 "SSH 미설정" 경고가 뜹니다.
4. **점검 스크립트 배치** — `ansible/scripts/rocky_linux/run_all.sh`,
   `ansible/scripts/ubuntu/run_all.sh`에 실제 KISA 점검 스크립트를 넣습니다.
   지금은 파이프라인 테스트용 예시 2줄(U-01, U-02)만 들어있습니다.
   출력 형식 계약은 `ansible/scripts/README.md`에 정리해뒀으니 계정관리/파일/
   서비스/패치/로그 담당자에게 그대로 공유하면 됩니다.

### 무엇이 바뀌었는지 (코드 변경 요약)

| 파일 | 변경 내용 |
|---|---|
| `models.py` | `Server`에 `ssh_user`, `ssh_port`, `ssh_key_path`, `ssh_become` 필드 추가 |
| `inventory.py` (신규) | 등록된 서버 → OS별로 그룹화한 Ansible YAML 인벤토리 생성 |
| `ansible/playbooks/diagnose.yml` (신규) | 스크립트 복사 → 실행 → JSON 회수 → 원격 흔적 삭제 |
| `ansible/scripts/*/run_all.sh` (신규, 예시) | 각 팀원의 점검 스크립트를 묶어 JSON으로 출력하는 진입점 |
| `blueprints/diagnosis.py` | `_run_scan_simulated()`(기존)과 `_run_scan_real()`(신규)을
  `USE_REAL_ANSIBLE` 설정값으로 분기. 실제 모드는 `ansible_runner.run()`을
  호출하고, 이벤트 콜백으로 서버별 완료 시점을 잡아 진행률(`run.completed`)을 갱신 |
| `blueprints/servers.py`, `templates/server_form.html` | SSH 접속정보 입력 필드 |
| `templates/diagnosis.html` | 현재 모드(시뮬레이션/실제) 배너, SSH 미설정 서버 경고 |

### 흐름 요약

```
진단 실행 버튼
  → generate_inventory()가 hosts.yml 새로 씀 (OS별 그룹화)
  → ansible_runner.run(playbook="diagnose.yml", inventory=hosts.yml, limit=선택한 서버)
      → 각 호스트: 스크립트 복사 → run_all.sh 실행 → result.json fetch → 원격 삭제
      → "결과 JSON 회수" 태스크 성공 이벤트마다 run.completed += 1 (진행률 폴링에 반영)
  → scan_results/<hostname>.json 각각 파싱 → ScanResult row 저장
  → run.status = completed
```

### 안 바뀌는 것 (그대로 재사용됨)

- 프론트엔드 진행률 폴링(`static/js/diagnosis.js`), `/diagnosis/status/<id>` API — 그대로 재사용
- 대시보드 히트맵·우선순위큐·점수 계산 — `ScanResult`만 채워지면 자동으로 반영됨
- 조치 승인 워크플로 — 이번 변경과 무관하게 그대로 동작 (다만 승인 시 실제 조치까지
  자동화하려면 `blueprints/approvals.py`의 `decide()` 승인 분기도 비슷한 방식으로
  Ansible 조치용 플레이북(`나장원` 담당, 아직 미개발) 호출로 바꿔야 합니다 — 진단과 별개 작업)

## 보고서 산출물

대시보드 우측 상단 "Excel 다운로드" / "PDF 다운로드" 버튼, 또는 서버 상세 페이지에서
서버 단위로 즉시 생성됩니다.

- **Excel (5시트)**: 표지 · 대시보드요약 · 항목별상세(위험도순 + 조건부서식) · 조치이력 · 승인이력
- **PDF**: 표지 + 요약 + 상세(취약 항목 위험도순) + 수동확인(N/A) 섹션

(착수보고서 원안은 PDF를 markdown → HTML → weasyprint로 만드는 것으로 되어 있으나,
이 환경에는 weasyprint 대신 순수 파이썬 라이브러리인 reportlab으로 동일한 섹션 구성을
직접 생성했습니다. 배포 서버에 weasyprint 설치가 가능하다면 그쪽으로 바꿔도 무방합니다.)

## 알아둘 점 (이번 프로토타입의 한계)

- 진단 실행은 **시뮬레이션**입니다. 실제 서버에 SSH로 접속하지 않고, 직전 최신 결과를
  새 타임스탬프로 재적재합니다. (위 "Ansible 연동 지점" 참고)
- 승인 후 조치 실행도 **시뮬레이션**입니다. 실제 백업 파일을 만들지 않고 경로 문자열만 기록하며,
  해당 항목을 즉시 "양호"로 전환합니다. 실제 연동 시 Ansible 조치용 플레이북 실행 결과를 받아
  반영하도록 `blueprints/approvals.py`의 `decide()` 함수 승인 분기를 교체하면 됩니다.
- U-42~47 및 CURRENT_SETTING_TEXT의 취약 설정 예시 문구는 데모 목적의 합성 데이터입니다
  (`catalog.py`, `seed_data.py` 상단 주석에 명시).
- 개발 서버(`app.run(debug=True)`)로 실행됩니다. 실제 배포 시 gunicorn 등 WSGI 서버 사용을
  권장합니다.
