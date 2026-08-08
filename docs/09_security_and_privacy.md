# 09. Security & Privacy

## 보안 원칙

실제 투자 데이터, 테스트·검증 데이터와 Secret을 분리하고 DB·계정정보·인증정보가 Git에 포함되지 않도록 관리합니다.

## Secret 관리

- `.env`, `.env.local` Git 제외
- `.env.example`에는 placeholder만 사용
- API Key·비밀번호를 로그에 출력하지 않음
- 실제 Secret을 소스와 문서에 포함하지 않음

## 데이터 분리

- 실제 투자 DB와 테스트·검증 DB 분리
- 실제 보유 수량·평단·개인 메모를 Git에 포함하지 않음
- 자동 회귀는 테스트 전용 데이터 사용
- 실제 UI 검증은 공개적으로 식별 가능한 자산으로 수행

## 외부 자료 관리

- 원문 전체보다 공개 메타데이터와 원문 링크 중심으로 관리
- 기사 전문 전체 미보관
- 공식 출처와 2차 출처 구분
- 자동 발견 후보와 정식 참고자료 분리
- 유료·비공개 자료 원문 미포함

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

## 최종 보안 검증

- 실제 투자 DB Git 제외 확인
- Secret·개인 계정정보 미포함 확인
- 검증용 데이터와 실제 데이터 경로 분리 확인
- 외부 자료 원문 전체 미저장 확인
- Git whitespace·민감파일 검사 PASS

---

[문서 목차](README.md) · [프로젝트 README](../README.md)
