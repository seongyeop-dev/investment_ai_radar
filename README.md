# Investment AI Radar

보유·관심 종목의 **공식 공시, 뉴스·중요 정보, 공개 참고자료, 경제·기업 일정**을 한곳에서 수집·검토하고, 출처와 근거를 기준으로 종목별 관리 방향과 변경 기반 브리핑을 정리하는 개인 투자정보 관리 웹 애플리케이션입니다.

> 자동 주문·자동매매·증권계좌 연동·수익 보장 기능은 제공하지 않습니다. 최종 투자 판단과 실제 주문은 사용자가 별도 금융 앱에서 수행합니다.

<p align="center">
  <img src="docs/images/01_오늘의_분석.png" alt="Investment AI Radar 오늘의 분석" width="100%">
</p>

## 프로젝트 정보

| 항목 | 내용 |
|:---|:---|
| 프로젝트 유형 | 개인 프로젝트 |
| 핵심 목적 | 여러 출처의 투자 정보를 하나의 검토 흐름으로 연결 |
| Backend | Python 3.12, FastAPI, SQLAlchemy, Alembic, Pydantic |
| Frontend | Next.js 16.3.0, React, TypeScript |
| Database | SQLite |
| Test / QA | pytest, Ruff, ESLint, Node Test Runner, Playwright |
| Operations | PowerShell, Windows Task Scheduler 구조 |
| 상태 | 기능 구현·통합 검증 완료 |

## 프로젝트 개요

개인 투자자는 보유·관심 종목을 관리하면서 공시, 뉴스, 기관 자료, 전문가 공개 자료와 경제·기업 일정을 여러 사이트에서 반복 확인하게 됩니다.

Investment AI Radar는 흩어진 정보를 단순 수집하는 데서 끝내지 않고 **출처 확인 → 중복 검토 → 사건 연결 → 변경 감지 → 브리핑 → 사용자 판단** 흐름으로 연결했습니다.

```text
공식 출처·공개 참고자료
→ 중요 정보·공시·일정 등록 및 확인
→ 중복·출처·검토 상태 관리
→ 통합 사건과 종목 연결
→ 변경 항목 선별
→ 브리핑·관리 방향 정리
→ 사용자 최종 판단
```

없는 정보는 임의로 추정하지 않습니다. 가격·시장 일정·Provider 등 연결되지 않은 데이터는 `미설정`, `비활성`, `데이터 부족`으로 표시합니다.

## 핵심 결과

- 분석 종목·거래 기록·출처·참고자료·공시·일정을 하나의 관리 흐름으로 연결
- 자동 발견 자료를 검토 대기 상태로 격리하고 사용자 확인 후 정식 자료로 승격
- 반복 뉴스·공시·참고자료를 `Information Event`와 통합 사건 단위로 연결
- state fingerprint를 기준으로 변경된 중요 정보만 브리핑 대상으로 선별
- 실제 투자 데이터와 검증 데이터를 분리하고 Secret·개인정보를 Git에서 제외
- 자동화 QA와 실제 UI 기능 시나리오 검증을 모두 완료

## 주요 기능

| 기능 영역 | 구현 내용 |
|:---|:---|
| 종목·거래 관리 | 분석 종목 등록·수정, 거래 기록, 보유 상태와 평균단가 replay |
| 출처·참고자료 | 공식 출처, 자동 구독, 전문가 공개 참고자료, 검토 대기 후보 |
| 중요 정보·공시 | URL 등록 전 확인, 중복 검사, 공식 공시 등록, 사건 연결 |
| 통합 사건 | 반복 뉴스·공시·참고자료를 사건 단위로 연결 |
| 경제·기업 일정 | 공식 일정 등록, 종목 연결, 다음 확인 일정 관리 |
| 변경 기반 브리핑 | 기존 상태와 비교해 변경된 중요 항목 중심으로 생성 |
| 위험 기준·관리 방향 | 사용자 위험 기준 제안·적용, 준비 상태와 관리 방향 표시 |
| 운영 상태 | Provider·DB·브리핑·자동화 연결 상태 확인 |

상세 화면과 기능별 검증 근거는 [03. Features](docs/03_features.md), 전체 QA 결과는 [05. Validation](docs/05_validation.md)에서 확인할 수 있습니다.

## 시스템 구조

```text
Next.js Web
    ↓ JSON API
FastAPI
    ↓
Service / Domain Rules
    ↓
SQLAlchemy Repository
    ↓
SQLite + Alembic

공식 URL / 공개 정보 / Provider
    ↓
등록 전 확인·중복 검사
    ↓
Reference / Information Event / Economic Event
    ↓
Portfolio 연결 / Briefing / 관리 방향
```

외부 Provider는 정보 수집과 조회 책임을 담당하며 거래 기록이나 Portfolio를 직접 변경하지 않습니다. 데이터 반영은 입력 검증과 사용자 확인 단계를 거쳐 처리합니다.

## 주요 문제 해결

### 등록 전 확인과 최종 등록 분리

외부 URL을 즉시 저장하지 않고 Preview와 Final Confirm을 분리해 출처·종목·중복 상태를 확인한 뒤 반영하도록 구성했습니다.

### 자동 발견 후보 격리

자동 발견 자료는 즉시 판단 근거로 사용하지 않고 검토 대기 상태에 두며, 승인된 자료만 정식 참고자료로 승격합니다.

### 반복 정보의 사건 단위 연결

뉴스·공시·참고자료를 개별 항목으로만 관리하지 않고 `Information Event`와 통합 사건으로 연결해 반복 확인을 줄였습니다.

### 변경 기반 브리핑

기존 사건의 state fingerprint와 현재 상태를 비교해 이미 확인한 내용보다 변경된 중요 정보를 우선 정리합니다.

### 임의 데이터 생성 방지

가격·환율·시장 일정 Provider가 연결되지 않은 경우 가짜 값을 만들지 않고 미설정·비활성·데이터 부족 상태를 그대로 노출합니다.

## 검증 결과

| 검사 | 결과 |
|:---|---:|
| Backend pytest | 625/625 PASS |
| Ruff lint | PASS |
| Ruff format | 220 files PASS |
| Web ESLint | PASS |
| Node UI tests | 43/43 PASS |
| Next.js production build | 18/18 routes PASS |
| Playwright E2E | 11/11 PASS |
| 실제 UI 기능 시나리오 | 13/13 PASS |
| E2E server cleanup | PASS |
| Git whitespace / 민감파일 검사 | PASS |

자동화 테스트는 코드·UI 계약을 검증하고, 13개 실제 UI 시나리오는 사용 흐름이 연결되어 동작하는지 확인했습니다.

## 프로젝트 범위

### 포함

- 종목·거래 기록 관리
- 공식 출처·공시·중요 정보·참고자료 관리
- 검토 대기 후보와 사용자 승인
- 통합 사건과 종목 연결
- 경제·기업 일정
- 변경 기반 브리핑
- 위험 기준과 규칙 기반 관리 방향
- 시스템 연결 상태와 로컬 자동화 구조
- Backend·Frontend·Browser 자동 회귀

### 설계상 제외

- 자동 주문·자동매매
- 증권계좌 인증·잔고 자동 동기화
- 투자 수익 보장과 자동 매수·매도 판단
- 기사·유료 문서 전문 저장
- 공개 인터넷 서비스용 인증·HTTPS
- 카카오톡·모바일 Push

이 항목들은 미완성 기능이 아니라 프로젝트의 책임 범위에서 의도적으로 제외한 영역입니다.

## 상세 문서

| 문서 | 내용 |
|:---|:---|
| [문서 목차](docs/README.md) | 상세 문서 전체 목록 |
| [01. Overview](docs/01_overview.md) | 개발 배경, 문제 정의, 목적과 최종 결과 |
| [02. Architecture](docs/02_architecture.md) | Web·API·Service·Repository와 시스템 경계 |
| [03. Features](docs/03_features.md) | 실제 구현 기능과 화면 |
| [04. Data Flow](docs/04_data_flow.md) | 등록·검토·사건 연결·브리핑 흐름 |
| [05. Validation](docs/05_validation.md) | 자동화 QA와 실제 UI 기능 검증 |
| [06. Project Scope](docs/06_project_scope.md) | 구현 범위와 설계상 제외 범위 |
| [07. Project Structure](docs/07_project_structure.md) | 저장소 구조와 핵심 경로 |
| [08. Operations](docs/08_operations.md) | 실행·QA·Scheduler·사용 흐름 |
| [09. Security & Privacy](docs/09_security_and_privacy.md) | Secret·데이터 분리·외부 자료 관리 |

## 완료 상태

Investment AI Radar는 기능 구현, 자동화 QA, 실제 UI 기능 시나리오 검증과 저장소 정리를 완료한 상태입니다.
