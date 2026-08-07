# 07. Project Structure

## 저장소 구조

```text
investment_ai_radar/
├─ .github/
│  └─ workflows/
├─ docs/
│  ├─ README.md
│  ├─ images/                 # 포트폴리오 대표 화면 15장
│  ├─ videos/                 # 편집 완료 기능 시연 13개
│  ├─ demo/
│  ├─ public/
│  ├─ validation/
│  ├─ 01_overview.md
│  ├─ 02_architecture.md
│  ├─ 03_features.md
│  ├─ 04_data_flow.md
│  ├─ 05_validation.md
│  ├─ 06_project_scope.md
│  ├─ 07_project_structure.md
│  ├─ 08_operations.md
│  ├─ 09_security_and_privacy.md
│  └─ 10_portfolio_media.md
├─ infrastructure/
├─ scripts/
├─ server/
│  ├─ alembic/
│  ├─ app/
│  │  ├─ api/
│  │  ├─ core/
│  │  ├─ models/
│  │  ├─ providers/
│  │  ├─ repositories/
│  │  ├─ schemas/
│  │  └─ services/
│  ├─ scripts/
│  ├─ tests/
│  └─ pyproject.toml
├─ tests/
├─ web/
│  ├─ scripts/
│  ├─ src/
│  │  ├─ app/
│  │  ├─ components/
│  │  ├─ config/
│  │  ├─ lib/
│  │  └─ types/
│  ├─ tests/
│  ├─ playwright.config.ts
│  └─ package.json
├─ workers/
├─ .env.example
├─ .gitignore
└─ README.md
```

## 핵심 경로

| 경로 | 역할 |
|:---|:---|
| `server/app/api` | HTTP endpoint와 API 계약 |
| `server/app/services` | 업무 규칙과 상태 전이 |
| `server/app/repositories` | DB 접근과 transaction |
| `server/app/providers` | 외부 공개 Provider adapter |
| `server/tests` | Backend 회귀 |
| `web/src/app` | Next.js route |
| `web/src/components` | 화면과 상호작용 |
| `web/src/lib` | API client와 공통 로직 |
| `web/tests` | UI 계약 회귀 |
| `web/tests/e2e` | Browser E2E |
| `scripts` | 로컬 운영·Scheduler·안전 도구 |
| `docs/images` | 대표 화면 15장 |
| `docs/videos` | 기능 시연 영상 13개 |

## 문서 구성

- `01~07`: 다른 포트폴리오 프로젝트와 공통으로 사용하는 핵심 문서 흐름
- `08_operations.md`: 이 프로젝트의 로컬 운영·Scheduler 특화 문서
- `09_security_and_privacy.md`: 투자 데이터·Secret·공개 범위 특화 문서
- `10_portfolio_media.md`: 이미지·영상 인덱스
- `demo/`: 공개 시연과 촬영 환경
- `public/`: 공개 Freeze·QA·Manifest 근거
- `validation/`: 공개 자산 기반 별도 검증 환경

## Git 제외 대상

```text
.env
.env.local
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
cache/
logs/
temp/
backup/
```

실제 투자 데이터와 런타임 산출물은 소스 저장소와 분리합니다.

## 공개 소스 구성

공개 저장소에는 애플리케이션 소스, 테스트, 마이그레이션, 운영 스크립트, 문서와 포트폴리오 미디어를 포함하고 실제 DB·Secret·개인 보유정보·로컬 런타임 산출물은 제외합니다.

---

[문서 목차](README.md) · [프로젝트 README](../README.md)
