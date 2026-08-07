# 공개 자산 검증 환경

## 목적

증권계좌나 개인 투자 DB를 가져오지 않고 공개적으로 식별 가능한 자산으로 애플리케이션 흐름을 검증하기 위한 별도 환경입니다.

## 검증 자산

- Samsung Electronics (`005930`, KRX, equity)
- Microsoft (`MSFT`, NASDAQ, equity)
- Bitcoin (`BTC`, UPBIT, crypto)

이 자산은 Web 화면을 통해 수동 등록합니다. 실제 보유 수량, 평균 매수가, 계정 자격 증명, API Key와 개인 포트폴리오 데이터는 필요하지 않습니다.

## Runtime 저장소

검증 DB는 다음 로컬 경로에서만 사용합니다.

```text
.local/portfolio_validation/portfolio_validation.db
```

`.local` 디렉터리와 SQLite DB는 Git에서 제외합니다.

## 시작과 종료

시작:

```text
scripts/start_portfolio_validation.ps1
```

종료:

```text
scripts/stop_portfolio_validation.ps1
```

시작 흐름은 Alembic migration을 적용하지만 가상 회사, 가상 공시, 가상 뉴스나 seeded portfolio item을 자동 삽입하지 않습니다.

## 검증 원칙

- 공개적으로 식별 가능한 실제 자산만 사용
- 개인 보유정보와 실제 계좌 데이터 미사용
- 검증 DB와 실제 투자 DB 경로 분리
- Git 추적 대상에서 로컬 DB 제외
- 자동 생성한 허위 시장·기업 정보를 검증 결과처럼 사용하지 않음

---

[문서 목차](../README.md) · [프로젝트 README](../../README.md)
