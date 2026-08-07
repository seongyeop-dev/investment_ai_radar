# Investment AI Radar

보유·관심 종목의 **공식 공시, 뉴스·중요 정보, 공개 참고자료, 경제·기업 일정**을 한곳에서 수집·검토하고, 출처와 근거를 기준으로 종목별 관리 방향을 정리하는 개인 투자정보 관리 프로젝트입니다.

> 이 프로젝트는 자동 주문·자동매매·증권계좌 연동·수익 보장을 제공하지 않습니다. 현재 관리 방향은 규칙 기반 검토이며, 최종 투자 판단과 실제 주문은 사용자가 별도 금융 앱에서 수행합니다.

![오늘의 분석](docs/images/01_오늘의_분석.png)

## 프로젝트 목적

투자자가 여러 사이트에서 반복해서 확인하던 정보를 하나의 흐름으로 묶는 것이 목표입니다.

```text
공식 출처·공개 참고자료 등록
→ 중요 정보·공시·일정 확인
→ 중복 제거와 출처 상태 관리
→ 통합 사건으로 연결
→ 종목별 영향과 다음 확인 일정 정리
→ 변경 기반 브리핑
→ 사용자 관리 기준 확인
```

핵심 원칙은 **없는 정보를 추정해서 채우지 않는 것**입니다. 데이터 제공자, 가격, 시장 일정, 이메일 등 운영 연결이 준비되지 않은 항목은 `미설정`, `비활성`, `데이터 부족` 상태로 그대로 표시합니다.

## 핵심 기능

- 분석 종목 등록·수정·상세 분석
- 거래 기록과 보유 상태 관리
- 공식 출처 등록·수정·자동 구독 관리
- 애널리스트·전문가 공개 참고자료 등록과 보관
- 자동 발견 후보의 검토 대기·승격·제외 흐름
- 중요 정보 URL 등록 전 확인과 최종 등록
- SEC 등 공식 공시 등록과 종목·통합 사건 연결
- 경제·기업 일정 등록과 종목별 다음 확인 일정 연결
- 변경 기반 브리핑 미리보기·생성
- 규칙 기반 종목 관리 방향과 위험 기준 관리
- 시장 브리핑·이메일 설정
- 출처·검증 상태와 시스템 연결 상태 확인

## 주요 화면

| 분석 종목 | 종목 상세 |
|---|---|
| ![분석 종목 목록](docs/images/02_분석_종목_목록.png) | ![종목 상세 분석](docs/images/03_마이크로소프트_종목_상세_분석.png) |

| 공식 공시 | 경제·기업 일정 |
|---|---|
| ![공식 공시](docs/images/06_공식_공시.png) | ![경제 기업 일정](docs/images/08_경제_기업_일정.png) |

| 변경 기반 브리핑 | 시스템 연결 상태 |
|---|---|
| ![변경 기반 브리핑](docs/images/09_변경_기반_브리핑.png) | ![시스템 연결 상태](docs/images/12_시스템_연결_상태.png) |

## 기능 시연 영상

| 번호 | 내용 | 영상 |
|---:|---|---|
| 01 | 분석 종목 등록 | [보기](docs/videos/01_분석_종목_등록.mp4) |
| 02 | 분석 종목 수정·종목 관리 방향 | [보기](docs/videos/02_분석_종목_수정_종목_관리_방향.mp4) |
| 03 | 고급 거래 기록 | [보기](docs/videos/03_분석_종목_고급_거래_기록.mp4) |
| 04 | 공식 출처 등록 및 수정 | [보기](docs/videos/04_공식_출처_등록_및_수정.mp4) |
| 05 | 출처 수정 및 관심 대상 등록 | [보기](docs/videos/05_출처_수정_및_관심_대상_등록.mp4) |
| 06 | 애널리스트 참고자료 등록 | [보기](docs/videos/06_애널리스트_참고자료_등록.mp4) |
| 07 | 검토 대기 자료 | [보기](docs/videos/07_검토_대기_자료.mp4) |
| 08 | 중요 정보 웹 등록·확인·통합 사건 연결 | [보기](docs/videos/08_중요_정보_웹_등록_검증_통합_사건_연결.mp4) |
| 09 | 공식 공시 웹 등록·확인·통합 사건 연결 | [보기](docs/videos/09_공식_공시_웹_등록_검증_통합_사건_연결.mp4) |
| 10 | 경제·기업 일정 웹 등록·종목 연결 | [보기](docs/videos/10_경제_기업_일정_웹_등록_종목_연결.mp4) |
| 11 | 변경 기반 브리핑 생성·핵심 정보 확인 | [보기](docs/videos/11_변경_기반_브리핑_생성_핵심_정보.mp4) |
| 12 | 종목 관리 방향·준비 상태·관리 기준 | [보기](docs/videos/12_종목_관리_방향_준비_상태_관리_기준.mp4) |
| 13 | 개인 설정·운영 상태·안전 기능 | [보기](docs/videos/13_개인_설정_운영_상태_안전_기능_확인.mp4) |

전체 이미지·영상 인덱스는 [docs/10_portfolio_media.md](docs/10_portfolio_media.md)에 정리했습니다.

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
출처·중복·상태 확인
    ↓
Information Event / Reference / Economic Event
    ↓
Portfolio 연결 / Briefing / 관리 방향
```

Provider가 포트폴리오나 거래 원장을 직접 수정하지 않도록 경계를 분리했습니다.

## 기술 스택

| 영역 | 기술 |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy, Alembic, Pydantic |
| Database | SQLite |
| Frontend | Next.js 16.3.0, React, TypeScript |
| Test | pytest, Node Test Runner, Playwright |
| Quality | Ruff, ESLint, TypeScript, Git whitespace check |
| Operations | PowerShell, Windows Task Scheduler 구조 |

## QA 상태

최종 공개 전 전체 회귀에서 다음 결과를 확인했습니다.

| 검사 | 확인 결과 |
|---|---:|
| Backend pytest | 625/625 PASS |
| Ruff lint | PASS |
| Ruff format | 216 files PASS |
| Web ESLint | PASS |
| Node UI | 43/43 PASS |
| Next.js production build | 18 routes PASS |
| Playwright Browser E2E | 11/11 PASS |
| Git whitespace | PASS |

기능 추가와 포트폴리오 정리 이후 전체 Backend 회귀를 다시 실행해 **625/625 PASS**를 확인했습니다. Ruff lint와 format, ESLint, UI 43/43, Next.js 18/18 routes, Playwright E2E 11/11과 E2E 서버 종료까지 최종 확인했습니다.

자세한 범위는 [docs/05_validation.md](docs/05_validation.md)를 참고하세요.

## 데이터와 공개 원칙

- 실제 투자 DB는 공개 저장소에 포함하지 않습니다.
- `.env`, `.env.local`, API Key, 이메일과 개인 계정 정보를 Git에서 제외합니다.
- 시연은 별도 격리 DB를 사용합니다.
- 대표 자산은 Samsung Electronics, Microsoft, Bitcoin처럼 공개적으로 식별 가능한 자산만 사용합니다.
- 기사 전문은 보관하지 않고 공개 메타데이터·링크·사용자 작성 요약을 중심으로 관리합니다.
- 실제 주문 생성·실행 기능은 지원하지 않습니다.

## 문서

- [01. 프로젝트 개요](docs/01_overview.md)
- [02. 아키텍처](docs/02_architecture.md)
- [03. 기능](docs/03_features.md)
- [04. 데이터 흐름](docs/04_data_flow.md)
- [05. QA와 검증 범위](docs/05_validation.md)
- [06. 프로젝트 범위와 제한사항](docs/06_project_scope.md)
- [07. 프로젝트 구조](docs/07_project_structure.md)
- [08. 운영](docs/08_operations.md)
- [09. 보안과 개인정보](docs/09_security_and_privacy.md)
- [10. 포트폴리오 미디어](docs/10_portfolio_media.md)
- [시연 가이드](docs/demo/README.md)

## 현재 상태

```text
FUNCTION_COMPLETE
PORTFOLIO_MEDIA_COMPLETE
FINAL_QA_COMPLETE
READY_FOR_INITIAL_GIT_COMMIT
```
