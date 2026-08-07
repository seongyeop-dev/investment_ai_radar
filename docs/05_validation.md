# 05. Validation

## 검증 기준

최종 공개본은 Backend, Frontend, Production Build, Browser E2E와 데이터 안전성을 분리해 검증했습니다.

실행하지 않은 외부 Provider·실기기 LAN·장기 Scheduler·외부 배포 항목은 PASS에 포함하지 않습니다.

## 최종 전체 회귀

기능 추가와 포트폴리오 정리 이후 2026-08-07 전체 회귀를 다시 실행했습니다.

| 영역 | 검사 | 최종 결과 |
|:---|:---|---:|
| Backend | pytest 전체 | 625/625 PASS |
| Backend | Ruff lint | PASS |
| Backend | Ruff format | 220 files PASS |
| Frontend | ESLint | PASS |
| Frontend | Node UI tests | 43/43 PASS |
| Build | Next.js production build | 18/18 routes PASS |
| Browser | Playwright E2E | 11/11 PASS |
| Runtime | E2E server cleanup | PASS |
| Git | whitespace / 공개 대상 / 민감파일 검사 | PASS |

## 기능별 회귀

포트폴리오 촬영을 위해 추가한 웹 등록 기능은 기능별 대상 회귀도 별도로 확인했습니다.

| 기능 | Backend 대상 회귀 | Frontend / Build |
|:---|:---:|:---|
| 중요 정보 웹 등록 | PASS | UI 40/40, Build 18/18 |
| 공식 공시 웹 등록 | PASS | UI 41/41, Build 18/18 |
| 경제·기업 일정 웹 등록 | PASS | UI 42/42, Build 18/18 |
| 변경 기반 브리핑 생성 | PASS | UI 43/43, Build 18/18 |

수정된 영역의 Ruff와 ESLint도 각 단계에서 PASS를 확인했습니다.

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

## 운영 환경 별도 검증

다음 항목은 실제 운영 환경에서 추가 확인이 필요하며, 현재 PASS 항목에 포함하지 않습니다.

- 실제 외부 Provider live smoke
- 실제 휴대전화 same-Wi-Fi LAN smoke
- 실제 Windows Scheduler task 연속 운영
- 실제 외부 배포
- 실제 투자 DB 운영 smoke
- 이메일·시장 일정 Provider 실연결

## 최종 검증 요약

자동 회귀와 공개 데이터 안전성 검사는 완료했습니다. 반면 외부 서비스·장기 운영·실제 사용자 DB에 의존하는 항목은 의도적으로 자동 QA와 분리했습니다.

---

[문서 목차](README.md) · [프로젝트 README](../README.md)
