# -*- coding: utf-8 -*-
"""
점검항목 카탈로그
------------------
출처: 프로젝트 참고자료 "2026 주요정보통신기반시설 기술적 취약점 분석·평가 방법 상세가이드"
      (Unix 서버 - 1.계정관리/2.파일 및 디렉터리관리/3.서비스관리/4.패치관리/5.로그관리,
       Web Application - 21개 항목)

U-01 ~ U-48, U-64 ~ U-67 항목명·위험도·카테고리는 security-platform 저장소의
실제 점검 스크립트(scripts/{rocky,ubuntu}/**/u_XX_*_check.sh) 헤더에 선언된
CATEGORY/EXPECTED_VALUE/RISK_LEVEL 값을 그대로 옮겼다 (check_id가 정확히 일치해야
run_all.sh가 회수한 JSON을 이 카탈로그에 매핑할 수 있다 - ScanResult.to_dict 참고).
U-49 ~ U-63은 아직 담당자가 점검 스크립트를 작성하지 않아 카탈로그에도 없다 -
스크립트가 추가되면 이 목록도 함께 갱신해야 한다.

Web Application 21항목은 가이드 원문 코드(CI/SI/DI/EP/IL/XS/CF/SF/BF/IA/IN/PR/PV/FU/FD/
IS/SN/CC/AE/AU/WM)를 그대로 사용했으며, 웹서버+DB 대상(webdb01)에만 적용한다.
"""

UNIX_ITEMS = [
    # (code, category, name, risk, guide)
    ("U-01", "계정 관리", "root 계정 원격 접속 제한", "H", "SSH sshd_config의 PermitRootLogin을 no로 설정 후 서비스 재시작"),
    ("U-02", "계정 관리", "비밀번호 관리정책 설정", "H", "/etc/login.defs 및 PAM 설정에서 최소 길이·복잡도·주기 정책 적용"),
    ("U-03", "계정 관리", "계정 잠금 임계값 설정", "H", "pam_tally2/pam_faillock으로 로그인 실패 5회 이하 잠금 설정"),
    ("U-04", "계정 관리", "비밀번호 파일 보호", "H", "/etc/shadow 소유자 root, 권한 400으로 변경"),
    ("U-05", "계정 관리", "root 이외의 UID가 '0' 금지", "H", "UID 0 계정을 조사해 root 이외 계정 삭제 또는 UID 변경"),
    ("U-06", "계정 관리", "사용자 계정 su 기능 제한", "H", "wheel 그룹에 su 허용 계정만 등록하고 /etc/pam.d/su 설정 적용"),
    ("U-07", "계정 관리", "불필요한 계정 제거", "L", "미사용 계정 목록 확인 후 userdel로 제거"),
    ("U-08", "계정 관리", "관리자 그룹에 최소한의 계정 포함", "M", "wheel/sudo 그룹 구성원을 필수 인원으로 최소화"),
    ("U-09", "계정 관리", "계정이 존재하지 않는 GID 금지", "L", "/etc/group 점검 후 미사용 GID 정리"),
    ("U-10", "계정 관리", "동일한 UID 금지", "M", "중복 UID 계정을 개별 UID로 재할당"),
    ("U-11", "계정 관리", "사용자 Shell 점검", "L", "미사용 계정 Shell을 /sbin/nologin으로 변경"),
    ("U-12", "계정 관리", "세션 종료 시간 설정", "L", "/etc/profile에 TMOUT=600 설정"),
    ("U-13", "계정 관리", "안전한 비밀번호 암호화 알고리즘 사용", "M", "/etc/login.defs ENCRYPT_METHOD을 SHA512로 설정"),

    ("U-14", "파일 및 디렉터리 관리", "root 홈, 패스 디렉터리 권한 및 패스 설정", "H", "PATH 환경변수에서 '.' 제거, 홈 디렉터리 권한 750 이하로 설정"),
    ("U-15", "파일 및 디렉터리 관리", "파일 및 디렉터리 소유자 설정", "H", "소유자가 없는 파일을 조사해 적절한 소유자로 재할당"),
    ("U-16", "파일 및 디렉터리 관리", "/etc/passwd 파일 소유자 및 권한 설정", "H", "chown root:root /etc/passwd; chmod 644 /etc/passwd"),
    ("U-17", "파일 및 디렉터리 관리", "시스템 시작 스크립트 권한 설정", "H", "/etc/rc.d 관련 파일 소유자 root, 권한 750 이하로 설정"),
    ("U-18", "파일 및 디렉터리 관리", "/etc/shadow 파일 소유자 및 권한 설정", "H", "chown root:root /etc/shadow; chmod 400 /etc/shadow"),
    ("U-19", "파일 및 디렉터리 관리", "/etc/hosts 파일 소유자 및 권한 설정", "H", "chown root:root /etc/hosts; chmod 600 /etc/hosts"),
    ("U-20", "파일 및 디렉터리 관리", "/etc/(x)inetd.conf 파일 소유자 및 권한 설정", "H", "chown root:root /etc/xinetd.conf; chmod 600"),
    ("U-21", "파일 및 디렉터리 관리", "/etc/(r)syslog.conf 파일 소유자 및 권한 설정", "H", "chown root:root /etc/rsyslog.conf; chmod 600"),
    ("U-22", "파일 및 디렉터리 관리", "/etc/services 파일 소유자 및 권한 설정", "H", "chown root:root /etc/services; chmod 644"),
    ("U-23", "파일 및 디렉터리 관리", "SUID, SGID, Sticky bit 설정 파일 점검", "H", "불필요한 SUID/SGID 비트를 chmod -s 로 제거"),
    ("U-24", "파일 및 디렉터리 관리", "사용자, 시스템 환경변수 파일 소유자 및 권한 설정", "H", "/etc/profile, .bashrc 등 소유자 root, 권한 644로 설정"),
    ("U-25", "파일 및 디렉터리 관리", "world writable 파일 점검", "H", "find / -perm -2 로 탐색 후 불필요한 쓰기 권한 제거"),
    ("U-26", "파일 및 디렉터리 관리", "/dev에 존재하지 않는 device 파일 점검", "H", "find /dev -type f 로 일반 파일 탐색 후 제거"),
    ("U-27", "파일 및 디렉터리 관리", "$HOME/.rhosts, hosts.equiv 사용 금지", "H", ".rhosts, hosts.equiv 파일 삭제 및 r계열 서비스 비활성화"),
    ("U-28", "파일 및 디렉터리 관리", "접속 IP 및 포트 제한", "H", "TCP Wrapper 또는 방화벽으로 접속 허용 IP/포트 제한"),
    ("U-29", "파일 및 디렉터리 관리", "hosts.lpd 파일 소유자 및 권한 설정", "L", "chown root:root /etc/hosts.lpd; chmod 600"),
    ("U-30", "파일 및 디렉터리 관리", "UMASK 설정 관리", "M", "/etc/profile에 umask 022 이상 설정"),
    ("U-31", "파일 및 디렉터리 관리", "홈 디렉토리 소유자 및 권한 설정", "M", "각 계정 홈 디렉터리 소유자를 해당 계정으로, 권한 700으로 설정"),
    ("U-32", "파일 및 디렉터리 관리", "홈 디렉토리로 지정한 디렉토리의 존재 관리", "M", "/etc/passwd 상 홈 디렉터리 경로 실존 여부 확인 및 생성"),
    ("U-33", "파일 및 디렉터리 관리", "숨겨진 파일 및 디렉토리 검색 및 제거", "L", "불필요한 숨김파일(.으로 시작) 탐색 후 검토·제거"),

    ("U-34", "서비스 관리", "Finger 서비스 비활성화", "H", "Finger 서비스 비활성화"),
    ("U-35", "서비스 관리", "공유 서비스의 익명 접근 제한", "H", "공유 서비스의 익명 접근 제한"),
    ("U-36", "서비스 관리", "rlogin/rsh/rexec 서비스 비활성화", "H", "rlogin/rsh/rexec 서비스 비활성화"),
    ("U-37", "서비스 관리", "crontab/at 명령 및 관련 파일 권한 설정", "H", "crontab/at 명령 750 이하·SUID 제거, 관련 파일 root 소유 및 640 이하"),
    ("U-38", "서비스 관리", "echo/discard/daytime/chargen 서비스 비활성화", "H", "echo/discard/daytime/chargen 서비스 비활성화"),
    ("U-39", "서비스 관리", "불필요한 NFS 서비스 비활성화", "H", "불필요한 NFS 서비스 비활성화"),
    ("U-40", "서비스 관리", "NFS 접근 통제 설정", "H", "NFS 접근 통제 설정 및 /etc/exports root 소유·644 이하"),
    ("U-41", "서비스 관리", "automountd/autofs 서비스 비활성화", "H", "automountd/autofs 서비스 비활성화"),
    ("U-42", "서비스 관리", "불필요한 RPC 서비스 비활성화", "H", "KISA 지정 불필요 RPC 서비스 비활성화"),
    ("U-43", "서비스 관리", "NIS 비활성화", "H", "NIS 비활성화 또는 불가피한 경우 NIS+ 사용"),
    ("U-44", "서비스 관리", "tftp/talk/ntalk 서비스 비활성화", "H", "tftp/talk/ntalk 서비스 비활성화"),
    ("U-45", "서비스 관리", "메일 서비스 최신 보안 버전 사용", "H", "메일 서비스 최신 보안 버전 사용"),
    ("U-46", "서비스 관리", "일반 사용자의 메일 큐/서비스 실행 제한", "H", "일반 사용자의 메일 큐/서비스 실행 제한"),
    ("U-47", "서비스 관리", "SMTP 릴레이 제한", "H", "SMTP 릴레이 제한 또는 릴레이 대상 접근 제어 설정"),
    ("U-48", "서비스 관리", "SMTP expn/vrfy 명령 제한", "M", "SMTP expn/vrfy 명령 제한"),
    ("U-49", "서비스 관리", "DNS 보안 버전 패치", "H", "DNS 미사용 또는 최신 버전으로 주기적 패치 관리 중"),
    ("U-50", "서비스 관리", "DNS Zone Transfer 제한", "H", "Zone Transfer가 허가된 대상으로만 제한됨"),
    ("U-51", "서비스 관리", "DNS 동적 업데이트 제한", "M", "동적 업데이트 비활성 또는 제한된 대상에만 허용"),
    ("U-52", "서비스 관리", "Telnet 서비스 비활성화", "M", "Telnet 서비스 비활성화(SSH 사용)"),
    ("U-53", "서비스 관리", "FTP 배너 정보 노출 제한", "L", "FTP 접속 배너에 서비스/버전 정보 노출 없음"),
    ("U-54", "서비스 관리", "평문 FTP 서비스 비활성화", "M", "평문 FTP 서비스 비활성화(SFTP/FTPS 권장)"),
    ("U-55", "서비스 관리", "ftp 계정 쉘 제한", "M", "ftp 계정에 로그인 불가 쉘(nologin/false) 부여"),
    ("U-56", "서비스 관리", "FTP 접속 IP 제한", "L", "특정 IP/호스트만 FTP 접속 허용"),
    ("U-57", "서비스 관리", "FTP root 직접 접속 차단", "M", "root 계정의 FTP 직접 접속 차단"),
    ("U-58", "서비스 관리", "SNMP 서비스 사용 여부 점검", "M", "SNMP 서비스 미사용"),
    ("U-59", "서비스 관리", "SNMP 버전 및 인증 강도", "H", "SNMPv3(인증+암호화) 이상 사용"),
    ("U-60", "서비스 관리", "SNMP Community String 복잡도", "M", "public/private 미사용 및 복잡도 기준 충족"),
    ("U-61", "서비스 관리", "SNMP 접근 대역 제한", "H", "SNMP 접근이 특정 대역으로 제한됨"),
    ("U-62", "서비스 관리", "로그온 경고 메시지 설정", "L", "서버 및 원격서비스 로그온 시 경고 메시지 출력"),
    ("U-63", "서비스 관리", "sudoers 파일 소유자 및 권한 설정", "M", "/etc/sudoers 소유자 root, 권한 640 이하"),
    ("U-64", "패치 관리", "주기적 보안 패치 및 벤더 권고사항 적용", "H", "패치 적용 정책을 수립하여 주기적으로 관리 중"),
    ("U-65", "로그 관리", "NTP/Chrony 등 시각 동기화 설정", "M", "NTP/Chrony 등 시각 동기화 설정 및 실제 동기화 상태 확인"),
    ("U-66", "로그 관리", "시스템 로깅 설정 및 로그 기록", "M", "내부 보안 정책에 따라 시스템 로깅 설정 및 로그 기록"),
    ("U-67", "로그 관리", "로그 파일 소유자 및 권한 관리", "M", "/var/log 내 로그 파일 root 소유 및 권한 644 이하"),
]

# 웹 서비스 26항목 - ansible/scripts/web/w_01~26_web_check.sh 실물 스크립트의
# CHECK_ID(WEB-01~26)·RISK_LEVEL 그대로 옮겼다 (이전엔 가이드 원문 예시코드
# WEB-CI/WEB-SI 등 21항목짜리 플레이스홀더였는데, check_id가 실제 스크립트와
# 안 맞아 결과가 전부 "알 수 없는 check_id"로 버려졌다 - 이제 스크립트가 실제로
# 있으니 그 출력과 1:1로 맞춘다). name/guide는 각 스크립트의 점검 로직·
# EXPECTED_VALUE를 그대로 옮겨적었다. 웹서버+DB(is_web_db) 대상에만 적용.
WEB_ITEMS = [
    ("WEB-01", "웹 서비스", "WAS 관리콘솔 노출 (Tomcat/IIS/JEUS 전용)", "H", "Tomcat/IIS/JEUS 대상 항목 - Apache 환경에는 해당 없음"),
    ("WEB-02", "웹 서비스", "불필요 서비스/포트 (Tomcat/IIS/JEUS 전용)", "H", "Tomcat/IIS/JEUS 대상 항목 - Apache 환경에는 해당 없음"),
    ("WEB-03", "웹 서비스", "기본 계정/설정 (Tomcat/IIS/JEUS 전용)", "H", "Tomcat/IIS/JEUS 대상 항목 - Apache 환경에는 해당 없음"),
    ("WEB-04", "웹 서비스", "디렉터리 인덱싱", "H", "httpd.conf Options 지시자에 Indexes 미포함"),
    ("WEB-05", "웹 서비스", "불필요한 CGI 실행 (mod_cgi)", "H", "mod_cgi(cgi_module) 비활성화"),
    ("WEB-06", "웹 서비스", ".htaccess 접근제어 미적용 (AllowOverride)", "H", "AllowOverride를 None이 아닌 값(AuthConfig 등)으로 설정"),
    ("WEB-07", "웹 서비스", "백업/샘플 파일 노출", "M", "웹 루트에 manual/sample/.bak/.old 등 불필요 파일 삭제"),
    ("WEB-08", "웹 서비스", "요청 본문 크기 제한 미흡 (DoS)", "L", "LimitRequestBody 설정"),
    ("WEB-09", "웹 서비스", "웹서버 프로세스 root 권한 구동", "H", "Apache User 지시자를 비root 계정으로 설정"),
    ("WEB-10", "웹 서비스", "오픈 프록시 설정", "H", "mod_proxy 미사용 또는 ProxyRequests Off"),
    ("WEB-11", "웹 서비스", "DocumentRoot 기본 경로 사용", "H", "DocumentRoot를 기본 경로(/var/www/html)가 아닌 경로로 분리(환경별 수동 판단)"),
    ("WEB-12", "웹 서비스", "심볼릭링크 추적 허용 (FollowSymLinks)", "M", "Options 지시자에 FollowSymLinks 미포함"),
    ("WEB-13", "웹 서비스", "불필요 기본 페이지 (Tomcat/IIS/JEUS 전용)", "H", "Tomcat/IIS/JEUS 대상 항목 - Apache 환경에는 해당 없음"),
    ("WEB-14", "웹 서비스", "웹서버 설정파일 권한 과다", "H", "httpd.conf 파일 권한 750 이하"),
    ("WEB-15", "웹 서비스", "설정파일 인증정보 평문저장 (Tomcat/IIS/JEUS 전용)", "H", "Tomcat/IIS/JEUS 대상 항목 - Apache 환경에는 해당 없음"),
    ("WEB-16", "웹 서비스", "서버 배너/버전정보 노출", "M", "ServerTokens Prod, ServerSignature Off"),
    ("WEB-17", "웹 서비스", "기본 제공 경로 노출 (/icons, /manual)", "M", "/icons, /manual 등 기본 제공 Alias 제거"),
    ("WEB-18", "웹 서비스", "WebDAV 활성화", "H", "mod_dav 미사용 및 Dav 지시자 Off"),
    ("WEB-19", "웹 서비스", "SSI(Server Side Includes) 실행 허용", "M", "Options 지시자에 Includes 미포함"),
    ("WEB-20", "웹 서비스", "HTTPS(SSL/TLS) 미적용", "H", "mod_ssl 로드 + SSLEngine on"),
    ("WEB-21", "웹 서비스", "HTTP→HTTPS 강제 리다이렉트 미설정", "M", "80번 포트 요청을 HTTPS로 리다이렉트"),
    ("WEB-22", "웹 서비스", "에러페이지 커스터마이징 미흡", "L", "400/401/403/404/500 ErrorDocument 설정"),
    ("WEB-23", "웹 서비스", "불필요 예제/테스트 페이지 (Tomcat/IIS/JEUS 전용)", "H", "Tomcat/IIS/JEUS 대상 항목 - Apache 환경에는 해당 없음"),
    ("WEB-24", "웹 서비스", "파일 업로드 검증 미흡", "M", "업로드 기능 추가 시 확장자·경로 검증 로직 점검 필요(현재 기능 미구현)"),
    ("WEB-25", "웹 서비스", "웹서버 패키지 보안패치 미적용", "H", "httpd 관련 패키지 최신 패치 적용"),
    ("WEB-26", "웹 서비스", "웹 로그 파일 권한 과다", "M", "로그 디렉터리 750 이하, 로그 파일 640 이하"),
]
