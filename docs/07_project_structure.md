# 07. 프로젝트 구조

```text
investment_ai_radar/
├─ .github/
│  └─ workflows/
├─ docs/
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

## 주요 역할

| 경로 | 역할 |
|---|---|
| `server/app/api` | HTTP endpoint와 계약 |
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
| `docs/images` | 대표 화면 |
| `docs/videos` | 기능 시연 영상 |

## Git 제외 대상

```text
.env
.env.local
.local/
*.db
*.sqlite*
node_modules/
.next/
.venv/
cache/
logs/
temp/
backup/
```

실제 투자 데이터와 런타임 산출물은 소스 저장소와 분리합니다.
