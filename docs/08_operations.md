# 08. Operations

## 운영 원칙

- Secret은 `.env` 또는 `.env.local`에만 저장하고 Git에서 제외합니다.
- 공개 저장소에는 `.env.example`만 포함합니다.
- 실제 투자 DB, 공개 시연 DB와 자동 회귀 DB를 분리합니다.
- 미설정 Provider는 임의 값으로 대체하지 않습니다.
- 실제 이메일은 이메일 Provider를 연결한 뒤에만 발송합니다.

## Backend QA

기존 가상환경이 준비된 개발 환경에서는 다음 검사를 사용합니다.

```powershell
& ".\server\.venv\Scripts\python.exe" -m pytest -q
& ".\server\.venv\Scripts\python.exe" -m ruff check .
& ".\server\.venv\Scripts\python.exe" -m ruff format --check .
```

## Web QA

```powershell
Set-Location ".\web"
npm run lint
npm run test:ui
npm run build
npm run test:e2e
```

처음 설치하는 환경에서는 lockfile을 기준으로 dependency를 설치해야 합니다.

## 시연 환경

포트폴리오 기능 촬영은 실제 투자 DB와 분리된 별도 recording session DB를 사용합니다.

```text
Web: 127.0.0.1:3011
API: 127.0.0.1:8011
DB: .local/recording_session/recording_session.db
```

실제 사용자 DB는 시연 흐름에서 접근하지 않습니다.

## Scheduler

- Windows Task Scheduler 연결 구조
- 중복 실행 lock
- UTF-8 로그
- DB revision guard
- 실패 상태 기록

실제 운영 Task 등록과 장기 연속 실행은 배포 환경에서 별도 확인합니다.

## 일상 사용 흐름

```text
오늘의 분석 확인
→ 중요 정보·공시·참고자료 확인
→ 검토 대기 자료 처리
→ 경제·기업 일정 확인
→ 변경 기반 브리핑 확인
→ 종목 관리 방향 확인
→ 실제 판단과 주문은 외부 금융 앱에서 수행
```

## 실패 처리 원칙

- Provider 실패 시 기존 Portfolio와 거래 기록을 임의로 수정하지 않음
- 미설정 Provider를 정상 상태처럼 표시하지 않음
- Scheduler 중복 실행을 lock으로 보호
- E2E 종료 후 테스트 서버 process cleanup
- DB revision이 맞지 않는 상태에서 임의 운영하지 않음

## 금지 사항

- 실제 DB를 공개 시연 DB로 복사
- Secret을 화면·로그·문서에 기록
- Provider가 거래 기록을 직접 수정
- 사용자 확인 없이 후보를 판단 근거로 승격
- 자동 주문 기능이 있는 것처럼 문서화

---

[문서 목차](README.md) · [프로젝트 README](../README.md)
