# 05. 검증 결과

## 검증 환경

최종 검증은 실제 투자 DB를 사용하지 않고 공개적으로 식별 가능한 자산을 별도 검증 DB에 등록해 수행했습니다.

검증 자산:

- Samsung Electronics (`005930`, KRX)
- Microsoft (`MSFT`, NASDAQ)
- Bitcoin (`BTC`, UPBIT)

실제 보유 수량, 평균 매수가, 계정 자격 증명, API Key와 개인 투자 데이터는 검증에 사용하지 않았습니다.

## 자동화 QA

| 영역 | 검사 | 결과 |
|:---|:---|---:|
| Backend | pytest 전체 | 625/625 PASS |
| Backend | Ruff lint | PASS |
| Backend | Ruff format | 220 files PASS |
| Frontend | ESLint | PASS |
| Frontend | Node UI tests | 43/43 PASS |
| Build | Next.js production build | 18/18 routes PASS |
| Browser | Playwright E2E | 11/11 PASS |
| Runtime | E2E server cleanup | PASS |
| Git | whitespace / 민감파일 검사 | PASS |

## 기능별 회귀

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

## 실제 UI 기능 검증

아래 13개 시나리오를 실제 UI에서 순서대로 실행해 기능 동작을 확인했습니다.


### 01. 분석 종목 등록

- 확인 내용: 종목 신규 등록과 목록 반영
- 결과: **PASS**

https://github.com/user-attachments/assets/a3a92ce7-66c1-47dd-945c-cf3e0b8aa2ea
### 02. 분석 종목 수정·관리 방향

- 확인 내용: 종목 수정과 관리 방향 상태 반영
- 결과: **PASS**

https://github.com/user-attachments/assets/1220ae1a-3450-4676-92ac-285f3b4624ab
### 03. 고급 거래 기록

- 확인 내용: 거래 입력과 보유 상태 계산 흐름
- 결과: **PASS**

https://github.com/user-attachments/assets/d06a5f1f-d0ae-4a06-9506-93588540bfa0
### 04. 공식 출처 등록·수정

- 확인 내용: 공식 출처 생성과 설정 변경
- 결과: **PASS**

https://github.com/user-attachments/assets/67778e6e-8d7a-4a82-85c1-6073e39431d5
### 05. 출처 수정·관심 대상 등록

- 확인 내용: 출처 변경과 관심 대상 연결
- 결과: **PASS**

https://github.com/user-attachments/assets/f72174c1-d4f8-4341-97de-b0b5d37551eb
### 06. 애널리스트 참고자료 등록

- 확인 내용: 공개 참고자료 메타데이터 등록
- 결과: **PASS**

https://github.com/user-attachments/assets/70687ec5-d306-46ba-b42c-085956407c8c
### 07. 검토 대기 자료

- 확인 내용: 후보 검토·승격·제외 흐름
- 결과: **PASS**

https://github.com/user-attachments/assets/f893039b-4ba2-4cf0-80c3-9d0786bb8f24
### 08. 중요 정보 웹 등록

- 확인 내용: 등록 전 확인·최종 등록·통합 사건 연결
- 결과: **PASS**

https://github.com/user-attachments/assets/5b24c288-5dd2-4ff8-a7e8-82fb3ce73cd6
### 09. 공식 공시 웹 등록

- 확인 내용: 공식 공시 확인·등록·통합 사건 연결
- 결과: **PASS**

https://github.com/user-attachments/assets/36be6be4-660a-4154-9216-a37db2c33f6e
### 10. 경제·기업 일정 등록

- 확인 내용: 공식 일정 등록과 종목 연결
- 결과: **PASS**

https://github.com/user-attachments/assets/1b25540b-290d-4db7-94a7-6c90791b1532
### 11. 변경 기반 브리핑

- 확인 내용: 변경 항목 선별과 브리핑 생성
- 결과: **PASS**

https://github.com/user-attachments/assets/4f80dd16-6d9e-4f00-9ec8-0b2474f8c593
### 12. 종목 관리 방향·관리 기준

- 확인 내용: 준비 상태·위험 기준·관리 방향 확인
- 결과: **PASS**

https://github.com/user-attachments/assets/e6edabda-a369-4837-9be1-042f6468e4e5
### 13. 개인 설정·운영 상태·안전 기능

- 확인 내용: 설정·Provider·DB·자동화 상태와 안전 경계 확인
- 결과: **PASS**

https://github.com/user-attachments/assets/1888abf3-2f54-47e6-bd9c-e25ddcd28db2
## 데이터 안전성

- 실제 투자 DB를 자동 회귀와 기능 검증에 사용하지 않음
- `.env.local` 내용 출력 없음
- 실제 계정·API Key·개인 보유정보 미사용
- 검증 DB와 실제 투자 DB 경로 분리
- Git 추적 대상에서 DB·Secret·로컬 런타임 산출물 제외
- 자동 생성한 허위 시장·기업 정보를 검증 결과로 사용하지 않음

## 검증 범위 경계

외부 Provider 실연결, 장기 Scheduler 연속 운영, 외부 인터넷 배포처럼 외부 서비스와 운영 환경에 종속되는 항목은 제품 설정에 따라 달라지는 운영 영역으로 분리했습니다.

이 프로젝트의 완료 검증은 **로컬 애플리케이션 기능, 데이터 처리, Browser E2E, 실제 UI 사용자 흐름과 데이터 안전성**을 기준으로 수행했습니다.

## 최종 검증 요약

```text
Backend pytest              625/625 PASS
Node UI                     43/43 PASS
Next.js build               18/18 routes PASS
Playwright E2E              11/11 PASS
실제 UI 기능 시나리오         13/13 PASS
민감파일·데이터 안전성 검사     PASS
```

---

[문서 목차](README.md) · [프로젝트 README](../README.md)
