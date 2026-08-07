# 공개 QA 요약

## 최종 전체 회귀

2026-08-07 기능 추가와 포트폴리오 정리 이후 전체 회귀를 다시 실행했습니다.

| 검사 | 최종 결과 |
|:---|---:|
| Backend pytest | 625/625 PASS |
| Ruff lint | PASS |
| Ruff format | 220 files PASS |
| Web ESLint | PASS |
| Node UI tests | 43/43 PASS |
| Next.js production build | 18/18 routes PASS |
| Playwright E2E | 11/11 PASS |
| E2E process cleanup | PASS |
| Git whitespace / 공개 대상 / 민감파일 검사 | PASS |

## 기능별 회귀

| 기능 | 결과 |
|:---|:---|
| 중요 정보 웹 등록 | Backend 대상 회귀 PASS / UI 40/40 / Build 18/18 |
| 공식 공시 웹 등록 | Backend 대상 회귀 PASS / UI 41/41 / Build 18/18 |
| 경제·기업 일정 웹 등록 | Backend 대상 회귀 PASS / UI 42/42 / Build 18/18 |
| 변경 기반 브리핑 생성 | Backend 대상 회귀 PASS / UI 43/43 / Build 18/18 |

수정된 영역의 Ruff와 ESLint도 각 단계에서 PASS를 확인했습니다.

## 데이터 안전성

- 자동 회귀에서 실제 투자 DB를 사용하지 않음
- 공개 포트폴리오에서 실제 계정·보유정보 미사용
- 시연 DB는 `.local` 아래 별도 격리
- `.env`와 Secret Git 제외
- 실제 주문 기능 미지원

## 운영 환경 별도 검증

- 외부 Provider live smoke
- 실제 휴대전화 LAN smoke
- 실제 Windows Scheduler 연속 운영
- 실제 외부 배포
- 실제 투자 DB 운영 smoke

실행하지 않은 항목은 PASS에 포함하지 않습니다.

---

[문서 목차](../README.md) · [프로젝트 README](../../README.md)
