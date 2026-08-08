# Investment AI Radar

보유·관심 종목의 **공식 공시, 뉴스·중요 정보, 공개 참고자료, 경제·기업 일정**을 한곳에서 수집·검토하고, 출처와 근거를 기준으로 종목별 관리 방향과 변경 기반 브리핑을 정리하는 개인 투자정보 관리 웹 애플리케이션입니다.

> 자동 주문·자동매매·증권계좌 연동·수익 보장 기능은 제공하지 않습니다. 최종 투자 판단과 실제 주문은 사용자가 별도 금융 앱에서 수행합니다.

<p align="center">
  <img src="docs/images/01_오늘의_분석.png" alt="Investment AI Radar 오늘의 분석" width="90%">
</p>

## 프로젝트 정보

| 항목 | 내용 |
|:---|:---|
| 구분 | 개인 프로젝트 |
| 목적 | 여러 출처의 투자 정보를 하나의 검토 흐름으로 연결 |
| Backend | Python, FastAPI, SQLAlchemy, Alembic, Pydantic |
| Frontend | Next.js 16.3.0, React, TypeScript |
| Database | SQLite |
| Test / QA | pytest, Ruff, ESLint, Node Test Runner, Playwright |
| Operations | PowerShell, Windows Task Scheduler 구조 |

## 프로젝트 개요

개인 투자자는 종목별 공시, 뉴스, 기관 자료, 전문가 공개 자료와 경제 일정을 여러 사이트에서 반복 확인해야 합니다. 이 과정에서 자료 누락, 중복 확인, 출처 혼재와 판단 근거의 단절이 발생할 수 있습니다.

Investment AI Radar는 이 정보를 다음 흐름으로 연결합니다.

```text
공식 출처·공개 참고자료 등록
→ 중요 정보·공시·일정 확인
→ 출처·중복·검토 상태 관리
→ 통합 사건과 종목 연결
→ 다음 확인 일정·관리 방향 정리
→ 변경 기반 브리핑
→ 사용자 최종 판단
```

핵심 원칙은 **없는 정보를 임의로 추정하지 않는 것**입니다. 가격·시장 일정·Provider 등 운영 연결이 준비되지 않은 항목은 `미설정`, `비활성`, `데이터 부족`으로 표시합니다.

## 핵심 결과

- 분석 종목·거래 기록·출처·참고자료·공시·일정을 하나의 종목 관리 흐름으로 연결
- 자동 발견 자료를 검토 대기 상태로 격리하고 사용자 승인 후 정식 자료로 승격
- 반복 뉴스·공시·참고자료를 `통합 사건` 단위로 연결
- 기존 상태 fingerprint를 기준으로 변경된 중요 정보만 브리핑 대상으로 선별
- 실제 투자 DB와 공개 시연·자동 회귀 DB를 분리
- 자동 회귀와 13개 기능 시연 시나리오를 함께 사용해 기능 흐름을 검증

## 주요 기능과 검증 증빙

이미지와 영상은 별도 미디어 목록에만 두지 않고, 실제 기능 설명과 같은 위치에서 확인할 수 있도록 연결했습니다.

### 1. 분석 종목·거래 기록·관리 방향

종목 등록·수정, 상세 분석, 거래 기록, 종목 관리 방향 준비 상태와 위험 기준을 관리합니다.

| 분석 종목 | 종목 상세 | 관리 방향 준비 상태 |
|:---:|:---:|:---:|
| ![분석 종목 목록](docs/images/02_분석_종목_목록.png) | ![종목 상세 분석](docs/images/03_마이크로소프트_종목_상세_분석.png) | ![종목 관리 방향 준비 상태](docs/images/04_종목_관리_방향_준비_상태.png) |

검증 영상:
[01 분석 종목 등록](docs/videos/01_분석_종목_등록.mp4) ·
[02 분석 종목 수정·관리 방향](docs/videos/02_분석_종목_수정_종목_관리_방향.mp4) ·
[03 고급 거래 기록](docs/videos/03_분석_종목_고급_거래_기록.mp4)

### 2. 공식 출처·자동 구독·참고자료

공식 출처와 관심 대상을 관리하고, 자동 발견 후보와 직접 등록 참고자료를 분리해 검토합니다.

| 공식 출처 | 자동 구독·검토 대기 | 참고자료 보관함 |
|:---:|:---:|:---:|
| ![공식 출처 관리](docs/images/11_출처_검증_상태_공식_출처_관리.png) | ![자동 구독 검토 대기](docs/images/11_1_출처_검증_상태_자동_구독_검토_대기.png) | ![참고자료 보관함](docs/images/11_2_출처_검증_상태_참고자료_보관함.png) |

검증 영상:
[04 공식 출처 등록·수정](docs/videos/04_공식_출처_등록_및_수정.mp4) ·
[05 출처 수정·관심 대상 등록](docs/videos/05_출처_수정_및_관심_대상_등록.mp4) ·
[06 애널리스트 참고자료 등록](docs/videos/06_애널리스트_참고자료_등록.mp4) ·
[07 검토 대기 자료](docs/videos/07_검토_대기_자료.mp4)

### 3. 중요 정보·공식 공시·통합 사건

URL 등록 전 확인, 중복 검사, 출처 확인과 종목 연결을 거쳐 뉴스·공시·참고자료를 통합 사건 단위로 관리합니다.

| 중요 정보 | 공식 공시 | 통합 사건 |
|:---:|:---:|:---:|
| ![중요 정보](docs/images/05_중요_정보_검증_상태.png) | ![공식 공시](docs/images/06_공식_공시.png) | ![통합 사건](docs/images/07_통합_사건.png) |

검증 영상:
[08 중요 정보 웹 등록·통합 사건 연결](docs/videos/08_중요_정보_웹_등록_검증_통합_사건_연결.mp4) ·
[09 공식 공시 웹 등록·통합 사건 연결](docs/videos/09_공식_공시_웹_등록_검증_통합_사건_연결.mp4)

### 4. 경제·기업 일정·변경 기반 브리핑

공식 일정과 예상 영향 경로를 종목에 연결하고, 기존 상태 fingerprint와 비교해 변경된 중요 정보를 브리핑으로 생성합니다.

| 경제·기업 일정 | 변경 기반 브리핑 |
|:---:|:---:|
| ![경제 기업 일정](docs/images/08_경제_기업_일정.png) | ![변경 기반 브리핑](docs/images/09_변경_기반_브리핑.png) |

검증 영상:
[10 경제·기업 일정 등록·종목 연결](docs/videos/10_경제_기업_일정_웹_등록_종목_연결.mp4) ·
[11 변경 기반 브리핑 생성](docs/videos/11_변경_기반_브리핑_생성_핵심_정보.mp4)

### 5. 위험 기준·개인 설정·시스템 상태

위험 기준 자동 제안, 시장 브리핑·알림 설정, 출처·Provider·DB·자동화 상태를 확인합니다.

| 위험 설정 | 브리핑·알림 설정 | 시스템 연결 상태 |
|:---:|:---:|:---:|
| ![위험 설정 자동 제안](docs/images/10_위험_설정_자동_제안.png) | ![시장 브리핑 알림 설정](docs/images/10_1_시장_브리핑_알림_설정.png) | ![시스템 연결 상태](docs/images/12_시스템_연결_상태.png) |

검증 영상:
[12 종목 관리 방향·관리 기준](docs/videos/12_종목_관리_방향_준비_상태_관리_기준.mp4) ·
[13 개인 설정·운영 상태·안전 기능](docs/videos/13_개인_설정_운영_상태_안전_기능_확인.mp4)

상세 기능별 설명과 동일한 증빙 연결은 [03. Features](docs/03_features.md)에 정리했습니다.

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

외부 공개 정보
    ↓
Provider / Web Registration
    ↓
등록 전 확인·중복·상태 검토
    ↓
Reference / Information Event / Economic Event
    ↓
Portfolio 연결 / Briefing / 관리 방향
```

Provider가 포트폴리오나 거래 원장을 직접 수정하지 않도록 책임 경계를 분리했습니다.

## 기술 스택

| 영역 | 기술 |
|:---|:---|
| Backend | Python 3.12, FastAPI, SQLAlchemy, Alembic, Pydantic |
| Database | SQLite |
| Frontend | Next.js 16.3.0, React, TypeScript |
| Test | pytest, Node Test Runner, Playwright |
| Quality | Ruff, ESLint, TypeScript, Git whitespace check |
| Operations | PowerShell, Windows Task Scheduler 구조 |

## 주요 문제 해결

### 등록 전 확인과 최종 등록 분리

외부 URL을 즉시 저장하지 않고 Preview와 Final Confirm을 분리해 사용자가 출처·종목·중복 상태를 확인한 뒤 등록하도록 구성했습니다.

### 자동 발견 후보 격리

자동 발견 자료는 즉시 판단 근거로 사용하지 않고 검토 대기 상태에 두며, 승인된 자료만 정식 참고자료로 승격합니다.

### 반복 정보의 사건 단위 연결

뉴스·공시·참고자료를 개별 항목으로만 관리하지 않고 `Information Event`와 통합 사건으로 연결해 반복 확인을 줄였습니다.

### 변경 기반 브리핑

기존 사건의 state fingerprint와 현재 상태를 비교해 이미 확인한 내용보다 변경된 중요 정보를 우선 정리합니다.

### 가짜 운영 데이터 방지

가격·환율·시장 일정 Provider가 연결되지 않은 경우 임의 값을 생성하지 않고 미설정·비활성·데이터 부족 상태를 그대로 노출합니다.

## 검증 결과

자동화 QA와 기능 시연 영상 검증을 분리해 기록합니다.

| 검사 | 최종 결과 |
|:---|---:|
| Backend pytest | 625/625 PASS |
| Ruff lint | PASS |
| Ruff format | 220 files PASS |
| Web ESLint | PASS |
| Node UI tests | 43/43 PASS |
| Next.js production build | 18/18 routes PASS |
| Playwright E2E | 11/11 PASS |
| 기능 시연 영상 검증 | 13/13 PASS |
| E2E server cleanup | PASS |
| Git whitespace / 공개 대상 / 민감파일 검사 | PASS |

13개 영상은 각 기능 시나리오를 실제 UI 흐름으로 재실행해 확인한 **수동 기능 검증 증빙**으로 사용합니다. 자동화 테스트 결과와 영상 기반 검증 결과를 같은 항목으로 합치지 않고 구분해 기록합니다.

자세한 검증 범위와 13개 영상별 검증 항목은 [05. Validation](docs/05_validation.md)에 정리했습니다.

## 프로젝트 범위

### 포함

- 종목·거래 기록 관리
- 공식 출처·공시·중요 정보·참고자료 관리
- 검토 대기 후보와 사용자 승인
- 통합 사건과 종목 연결
- 경제·기업 일정
- 변경 기반 브리핑
- 위험 기준과 규칙 기반 관리 방향
- 자동 회귀와 로컬 운영 구조

### 제외

- 자동 주문·자동매매
- 증권계좌 인증·연동
- 잔고 자동 동기화
- 투자 수익 보장과 자동 매수·매도 판단
- 기사·유료 문서 전문 저장
- 인증·HTTPS를 갖춘 외부 공개 서비스

## 데이터와 공개 원칙

- 실제 투자 DB, 개인 보유정보와 계정정보는 공개 저장소에 포함하지 않습니다.
- `.env`, `.env.local`, API Key와 Secret은 Git에서 제외합니다.
- 공개 시연·포트폴리오 촬영·자동 회귀 환경을 실제 투자 DB와 분리합니다.
- 외부 자료는 원문 전체보다 URL·출처·핵심 주장·메타데이터 중심으로 관리합니다.
- 완료하지 않은 운영 검증은 PASS로 표시하지 않습니다.

## 상세 문서

| 번호 | 문서 | 내용 |
|:---:|:---|:---|
| - | [문서 목차](docs/README.md) | 전체 상세 문서와 읽는 순서 |
| 01 | [Overview](docs/01_overview.md) | 개발 배경, 문제 정의, 목적과 최종 결과 |
| 02 | [Architecture](docs/02_architecture.md) | Web·API·Service·Repository와 데이터 경계 |
| 03 | [Features](docs/03_features.md) | 실제 구현 기능과 기능별 이미지·영상 증빙 |
| 04 | [Data Flow](docs/04_data_flow.md) | 등록·검토·사건 연결·브리핑 흐름 |
| 05 | [Validation](docs/05_validation.md) | 자동 회귀와 13개 기능 시연 영상 검증 |
| 06 | [Project Scope](docs/06_project_scope.md) | 포함·제외·운영 확인 범위 |
| 07 | [Project Structure](docs/07_project_structure.md) | 실제 저장소 구조와 핵심 경로 |
| 08 | [Operations](docs/08_operations.md) | QA, 시연 환경, Scheduler와 운영 원칙 |
| 09 | [Security & Privacy](docs/09_security_and_privacy.md) | Secret·DB·외부 자료·Git 공개 원칙 |
| 10 | [Portfolio Media](docs/10_portfolio_media.md) | 전체 미디어 인덱스 |
| 시연 | [Demo Guide](docs/demo/README.md) | 공개 시연 순서와 촬영 기준 |

## 완료 상태

기능 구현, 포트폴리오 미디어 정리, 자동화 QA, 13개 기능 시연 영상 검증, 개별 GitHub `main` 정리와 Portfolio Hub 연결까지 완료했습니다.
