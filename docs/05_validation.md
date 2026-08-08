# 05. Validation

## 검증 기준

최종 공개본은 다음 세 가지를 분리해 검증했습니다.

1. Backend·Frontend·Build·Browser 자동화 QA
2. 13개 실제 UI 기능 시나리오의 영상 기반 수동 검증
3. 실제 투자 데이터와 Secret이 공개본에 포함되지 않는 데이터 안전성 검증

실행하지 않은 외부 Provider·실기기 LAN·장기 Scheduler·외부 배포 항목은 PASS에 포함하지 않습니다.

## 자동화 QA

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

## 기능별 자동 회귀

포트폴리오 촬영을 위해 추가한 웹 등록 기능은 기능별 대상 회귀도 별도로 확인했습니다.

| 기능 | Backend 대상 회귀 | Frontend / Build |
|:---|:---:|:---|
| 중요 정보 웹 등록 | PASS | UI 40/40, Build 18/18 |
| 공식 공시 웹 등록 | PASS | UI 41/41, Build 18/18 |
| 경제·기업 일정 웹 등록 | PASS | UI 42/42, Build 18/18 |
| 변경 기반 브리핑 생성 | PASS | UI 43/43, Build 18/18 |

수정된 영역의 Ruff와 ESLint도 각 단계에서 PASS를 확인했습니다.

## 기능 시연 영상 검증

포트폴리오 촬영 과정에서 아래 13개 기능 시나리오를 실제 UI 흐름으로 재실행해 확인했습니다.

영상은 단순 홍보 자료가 아니라 **기능 동작을 직접 확인한 수동 검증 증빙**으로 사용합니다.

| 번호 | 검증 기능 | 확인 내용 | 증빙 영상 | 결과 |
|---:|:---|:---|:---|:---:|
| 01 | 분석 종목 등록 | 종목 신규 등록과 목록 반영 | [영상](videos/01_분석_종목_등록.mp4) | PASS |
| 02 | 분석 종목 수정·관리 방향 | 종목 수정과 관리 방향 상태 반영 | [영상](videos/02_분석_종목_수정_종목_관리_방향.mp4) | PASS |
| 03 | 고급 거래 기록 | 거래 입력과 보유 상태 계산 흐름 | [영상](videos/03_분석_종목_고급_거래_기록.mp4) | PASS |
| 04 | 공식 출처 등록·수정 | 공식 출처 생성과 설정 변경 | [영상](videos/04_공식_출처_등록_및_수정.mp4) | PASS |
| 05 | 출처 수정·관심 대상 등록 | 출처 변경과 관심 대상 연결 | [영상](videos/05_출처_수정_및_관심_대상_등록.mp4) | PASS |
| 06 | 애널리스트 참고자료 등록 | 공개 참고자료 메타데이터 등록 | [영상](videos/06_애널리스트_참고자료_등록.mp4) | PASS |
| 07 | 검토 대기 자료 | 후보 검토·승격·제외 흐름 | [영상](videos/07_검토_대기_자료.mp4) | PASS |
| 08 | 중요 정보 웹 등록 | 등록 전 확인·최종 등록·통합 사건 연결 | [영상](videos/08_중요_정보_웹_등록_검증_통합_사건_연결.mp4) | PASS |
| 09 | 공식 공시 웹 등록 | 공식 공시 확인·등록·통합 사건 연결 | [영상](videos/09_공식_공시_웹_등록_검증_통합_사건_연결.mp4) | PASS |
| 10 | 경제·기업 일정 등록 | 공식 일정 등록과 종목 연결 | [영상](videos/10_경제_기업_일정_웹_등록_종목_연결.mp4) | PASS |
| 11 | 변경 기반 브리핑 | 변경 항목 선별과 브리핑 생성 | [영상](videos/11_변경_기반_브리핑_생성_핵심_정보.mp4) | PASS |
| 12 | 종목 관리 방향·관리 기준 | 준비 상태·위험 기준·관리 방향 확인 | [영상](videos/12_종목_관리_방향_준비_상태_관리_기준.mp4) | PASS |
| 13 | 개인 설정·운영 상태·안전 기능 | 설정·Provider·DB·자동화 상태와 안전 경계 확인 | [영상](videos/13_개인_설정_운영_상태_안전_기능_확인.mp4) | PASS |

### 영상 검증 결과

```text
기능 시연 영상 검증: 13/13 PASS
```

자동화 테스트는 코드와 UI 계약을 검증하고, 13개 영상은 실제 사용자 흐름이 연결되어 동작하는지 확인하는 수동 기능 검증으로 역할을 구분합니다.

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
- 13개 영상과 스크린샷에도 실제 투자 DB·Secret·계정정보를 사용하지 않음

## 운영 환경 별도 검증

다음 항목은 실제 운영 환경에서 추가 확인이 필요하며, 현재 PASS 항목에 포함하지 않습니다.

- 실제 외부 Provider live smoke
- 실제 휴대전화 same-Wi-Fi LAN smoke
- 실제 Windows Scheduler task 연속 운영
- 실제 외부 배포
- 실제 투자 DB 운영 smoke
- 이메일·시장 일정 Provider 실연결

## 최종 검증 요약

```text
Backend pytest              625/625 PASS
Node UI                     43/43 PASS
Next.js build               18/18 routes PASS
Playwright E2E              11/11 PASS
기능 시연 영상 검증          13/13 PASS
공개 데이터·민감파일 검사     PASS
```

자동 회귀와 실제 UI 흐름 검증을 함께 사용하되, 외부 서비스·장기 운영·실제 사용자 DB에 의존하는 미실행 항목은 완료 검증과 분리했습니다.

---

[문서 목차](README.md) · [프로젝트 README](../README.md)
