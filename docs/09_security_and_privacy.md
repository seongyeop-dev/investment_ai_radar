# 09. Security & Privacy

## 보안 원칙

실제 투자 데이터, 공개 시연 데이터, 자동 회귀 데이터를 분리하고 Secret·개인정보·DB가 Git에 포함되지 않도록 관리합니다.

## Secret 관리

- `.env`, `.env.local` Git 제외
- `.env.example`에는 placeholder만 사용
- API Key·비밀번호를 로그에 출력하지 않음
- GitHub에 실제 Secret을 포함하지 않음

## 데이터 분리

- 실제 투자 DB와 시연 DB 분리
- 공개 저장소에 DB 미포함
- 실제 보유 수량·평단·개인 메모 미포함
- 자동 회귀는 테스트 전용 데이터 사용

## 외부 자료 관리

- 공개 메타데이터와 원문 링크 중심
- 기사 전문 전체 미보관
- 공식 출처와 2차 출처 구분
- 자동 발견 후보와 정식 참고자료 분리
- 유료·비공개 자료 원문을 공개 저장소에 포함하지 않음

## 변경 안전성

- 삭제 대신 archive·soft void 사용 영역 분리
- transaction 경계
- 중복·충돌 보호
- Alembic revision guard
- Scheduler 중복 실행 lock
- E2E process cleanup

## Git 제외 규칙

```text
.env
.env.*
.local/
*.db
*.db-*
*.sqlite*
*.sqlite3*
*.pem
*.key
node_modules/
.next/
.venv/
logs/
temp/
backup/
```

## 공개 원칙

1. 실제 투자 데이터는 공개하지 않습니다.
2. 완료하지 않은 운영 검증을 PASS로 표기하지 않습니다.
3. 자동 주문·수익 보장 기능이 있는 것처럼 설명하지 않습니다.
4. 공개 미디어에는 실제 계정·Secret·개인 경로를 노출하지 않습니다.
5. 대표 자산은 공개적으로 식별 가능한 자산을 사용하고 개인 보유정보는 사용하지 않습니다.

---

[문서 목차](README.md) · [프로젝트 README](../README.md)
