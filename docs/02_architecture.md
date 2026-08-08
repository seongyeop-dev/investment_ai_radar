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

공식 URL / 공개 정보 / Provider
        ↓
등록 전 확인·중복 검사
        ↓
검토 가능한 구조화 데이터
```

## 주요 구성 요소

### Web

- 사용자 입력과 상태 확인
- 등록 전 Preview와 Final Confirm 분리
- 오류·중복·미설정 상태 표시
- 브리핑과 관리 방향 조회
- 모바일 화면과 키보드 Focus 대응

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

자동 발견 후보와 정식 참고자료를 분리합니다. 후보는 사용자 검토 전 분석 근거로 사용하지 않습니다.

### Information Event

중요 정보, 공시와 참고자료를 사건 단위로 연결하고 Portfolio와의 관계를 관리합니다.

### Economic Event

공식 발표 일정, 예상 영향 경로와 발표 전 확인 항목을 종목과 연결합니다.

### Briefing

기존 사건의 state fingerprint를 사용해 변경된 항목 중심으로 브리핑을 생성하고 중복 항목을 제외합니다.

## 시스템 경계

- Provider는 외부 정보 수집·조회 책임을 담당하며 거래 기록이나 Portfolio를 직접 수정하지 않습니다.
- 자동 발견 후보와 사용자 확인이 끝난 참고자료를 분리합니다.
- 외부 URL 등록은 Preview와 Final Confirm 단계를 거쳐 반영합니다.
- 실제 투자 데이터와 테스트·검증 데이터를 분리합니다.
- 외부 문서는 원문 전체보다 URL·메타데이터·핵심 주장 중심으로 관리합니다.
- 시스템은 정보 수집·검토·관리와 브리핑을 지원하며 실제 주문은 사용자가 외부 금융 앱에서 수행합니다.

## 설계 결과

외부 데이터 오류나 Provider 실패가 기존 Portfolio·거래 기록을 임의로 변경하지 않도록 책임을 분리했고, 정보 수집 단계와 사용자 판단 단계를 명확히 구분했습니다.

---

[문서 목차](README.md) · [프로젝트 README](../README.md)
