# 08. Operations

## 운영 환경

- Backend: Python 3.12 / FastAPI
- Frontend: Next.js 16.3.0
- Database: SQLite + Alembic
- Local automation: PowerShell / Windows Task Scheduler 구조
- Secret: `.env`, `.env.local`로 분리
- 미설정 Provider: 임의 값으로 대체하지 않고 상태를 그대로 표시

## Backend QA

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

Dependency는 lockfile을 기준으로 설치합니다.

## Scheduler

- Windows Task Scheduler 연결 구조
- 중복 실행 lock
- UTF-8 로그
- DB revision guard
- 실패 상태 기록

Scheduler와 Provider 상태는 시스템 연결 상태 화면에서 확인할 수 있도록 구성했습니다.

## 사용 흐름

```text
오늘의 분석 확인
→ 중요 정보·공시·참고자료 확인
→ 검토 대기 자료 처리
→ 경제·기업 일정 확인
→ 변경 기반 브리핑 확인
→ 종목 관리 방향 확인
→ 사용자가 최종 판단
→ 실제 주문은 외부 금융 앱에서 수행
```

## 실패 처리 원칙

- Provider 실패 시 기존 Portfolio와 거래 기록을 임의로 수정하지 않음
- 미설정 Provider를 정상 상태처럼 표시하지 않음
- Scheduler 중복 실행을 lock으로 보호
- E2E 종료 후 테스트 서버 process cleanup
- DB revision이 맞지 않으면 자동 실행을 중단하고 상태를 기록
- 중복 등록과 상태 충돌은 구조화된 오류로 반환

## 운영 결과

애플리케이션 기능, 데이터 처리, 상태 표시와 자동화 보호 로직은 자동 회귀와 실제 UI 기능 시나리오를 통해 검증했습니다.

---

[문서 목차](README.md) · [프로젝트 README](../README.md)
