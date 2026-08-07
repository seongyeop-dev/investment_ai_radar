# 공개 시연 데이터 환경

## 목적

실제 투자 DB와 분리된 환경에서 화면과 기능을 확인하기 위한 로컬 시연 데이터 구조입니다.

프로젝트에는 초기 공개 검토와 최종 포트폴리오 촬영을 위한 서로 다른 격리 환경이 있습니다.

## Synthetic Public Demo

초기 QA와 공개 화면 검토를 위한 합성 데이터 환경입니다.

```text
.local/public_demo/public_demo.db
```

- `DEMO-*` 형식의 합성 식별자 사용
- 외부 Provider·Email·AI 자동화 비활성
- 실제 투자 DB 접근 없음

## Portfolio Recording Session

최종 포트폴리오 영상 촬영에 사용한 환경입니다.

```text
.local/recording_session/recording_session.db
```

대표 자산:

- Samsung Electronics (`005930`, KRX)
- Microsoft (`MSFT`, NASDAQ)
- Bitcoin (`BTC`, UPBIT)

공개적으로 식별 가능한 자산을 사용하지만 개인 보유 수량·평단·계정 정보는 사용하지 않습니다.

## 저장소 정책

`.local/`과 SQLite DB는 Git에서 제외합니다.

## 안전장치

- 실제 투자 DB와 경로 분리
- 외부 Provider 자동 요청 비활성 가능
- 이메일 발송 비활성
- 실제 주문 기능 미지원
- 사용자가 입력한 공개 URL과 메타데이터 중심
- 프로세스 종료 시 시연 DB 보존

## 공개 포트폴리오

GitHub에는 DB 자체를 포함하지 않고, 대표 화면과 편집 영상만 `docs/images`, `docs/videos`에 포함합니다.

---

[문서 목차](../README.md) · [프로젝트 README](../../README.md)
