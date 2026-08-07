# 05. QA와 검증 범위

## 최종 전체 회귀

2026-08-07 포트폴리오 공개본에서 다시 실행해 확인한 최종 결과입니다.

| 영역 | 검사 | 결과 |
|---|---|---:|
| Backend | pytest 전체 | 625/625 PASS |
| Backend | Ruff lint | PASS |
| Backend | Ruff format | 216 files PASS |
| Frontend | ESLint | PASS |
| Frontend | Node UI | 43/43 PASS |
| Build | Next.js production build | 18 routes PASS |
| Browser | Playwright E2E | 11/11 PASS |
| Git | whitespace check | PASS |
| Runtime | E2E server cleanup | PASS |

## 이후 기능별 회귀

전체 기준선 이후 포트폴리오 촬영을 위해 추가된 기능은 대상 회귀를 별도로 확인했습니다.

| 기능 | Backend 대상 회귀 | Frontend / Build |
|---|---|---|
| 중요 정보 웹 등록 | PASS | UI 40/40, Build 18/18 |
| 공식 공시 웹 등록 | PASS | UI 41/41, Build 18/18 |
| 경제·기업 일정 웹 등록 | PASS | UI 42/42, Build 18/18 |
| 변경 기반 브리핑 생성 | PASS | UI 43/43, Build 18/18 |

수정된 영역의 Ruff와 ESLint도 각 단계에서 PASS를 확인했습니다.

## 최종 공개 QA 상태

기능 추가와 포트폴리오 정리 이후 전체 회귀를 다시 실행했습니다.

- Backend pytest: 625/625 PASS
- Ruff lint: PASS
- Ruff format: 220 files PASS
- Web ESLint: PASS
- Node UI: 43/43 PASS
- Next.js production build: 18/18 routes PASS
- Playwright E2E: 11/11 PASS
- E2E server cleanup: PASS

Git whitespace 검사는 초기 commit 직전 최종 파일 집합에서 다시 확인합니다.
## Browser E2E 주요 범위

- 후보 pagination과 필터 초기화
- total 감소 후 유효 페이지 복구
- 상세 열기·닫기 중복 요청 방지
- 발행일 확인과 참고자료 승격
- 최종 후보 상태 보호
- 중복 제출 차단
- 구조화된 409 처리
- stale response 방지
- 390px 모바일 화면
- Dialog focus trap과 trigger 복원
- 모바일 navigation focus 이동

## 데이터 안전성

- 실제 투자 DB를 자동 회귀에서 사용하지 않음
- `.env.local` 내용 출력 없음
- 공개 시연은 별도 SQLite DB 사용
- 실제 계정·API Key·개인 보유정보 미사용
- 외부 Provider 연결 여부와 자동 회귀를 분리

## Deferred 운영 검증

- 실제 외부 Provider live smoke
- 실제 휴대전화 LAN smoke
- 실제 Windows Scheduler task 연속 운영
- 실제 외부 배포
- 실제 투자 DB 운영 smoke

이 항목은 실행하기 전까지 PASS로 간주하지 않습니다.
