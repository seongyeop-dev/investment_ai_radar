# 02. Architecture

## 전체 구조

```text
┌─────────────────────────────────────┐
│ Next.js Web                         │
│ Dashboard / Portfolio / Events      │
│ Sources / Briefings / Settings      │
└──────────────────┬──────────────────┘
                   │ JSON API
┌──────────────────▼──────────────────┐
│ FastAPI                             │
│ Router → Service → Repository       │
└──────────────────┬──────────────────┘
                   │
┌──────────────────▼──────────────────┐
│ Domain                              │
│ Portfolio / Position / Disclosure   │
│ Reference / Event / Risk / Briefing │
└──────────────────┬──────────────────┘
                   │
┌──────────────────▼──────────────────┐
│ SQLite + Alembic                    │
└─────────────────────────────────────┘

공개 정보 / 공식 URL / Provider
        ↓
등록 전 확인·중복 확인
        ↓
검토 가능한 구조화 데이터
```

## 주요 구성 요소

### Web

- 사용자 입력과 상태 확인
- 등록 전 Preview와 Final Confirm 분리
- 오류·중복·미설정 상태 표시
- 브리핑과 관리 방향 조회
- 모바일 화면과 키보드 Focus 검증

### API

- HTTP 계약과 입력 검증
- 구조화된 오류 응답
- Preview와 Confirm 요청 분리
- 조회와 쓰기 경계 분리

### Service

- 중복·상태 전이·검토 규칙
- URL 정규화
- Portfolio 연결
- Risk·관리 방향 계산
- Briefing 대상 선별과 중복 방지
- Scheduler 실행 제어

### Repository

- SQLAlchemy 기반 영속화
- Transaction 경계
- 동시성·중복 보호
- Alembic revision 관리

## 주요 데이터 영역

### Portfolio / Position Ledger

Portfolio는 관리 대상 종목을 나타냅니다. 거래 기록은 매수·매도 이력을 저장하고 replay 방식으로 보유 수량과 평균단가를 계산합니다.

### Reference / Candidate

자동 발견 후보와 정식 참고자료를 분리합니다. 후보는 검토 전 분석 근거로 사용하지 않습니다.

### Information Event

중요 정보, 공시와 참고자료를 사건 단위로 연결하고 Portfolio와의 관계를 관리합니다.

### Economic Event

공식 발표 일정, 예상 영향 경로와 발표 전 확인 항목을 종목과 연결합니다.

### Briefing

기존 사건의 상태 fingerprint를 사용해 변경된 항목 중심으로 브리핑을 생성하고 중복 항목을 제외합니다.

## 책임 경계

- Provider가 거래 기록이나 Portfolio를 직접 수정하지 않음
- 자동 발견 후보와 승인된 참고자료 분리
- Preview와 Final Confirm 분리
- 실제 투자 DB와 시연·자동 회귀 DB 분리
- 외부 문서 전문 전체 미보관
- 실제 주문 생성·실행 기능 미지원

## 설계 포인트

이 구조는 외부 데이터가 불완전하거나 Provider가 실패해도 사용자의 포트폴리오와 거래 기록을 임의로 변경하지 않도록 구성했습니다.

또한 정보 수집 단계와 사용자 판단 단계를 분리해, 시스템이 투자 판단을 자동 확정하지 않도록 범위를 제한했습니다.

---

[문서 목차](README.md) · [프로젝트 README](../README.md)
