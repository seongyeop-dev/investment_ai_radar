# 07. Project Structure

## 저장소 구조

```text
investment_ai_radar/
├─ .github/
│  └─ workflows/
├─ docs/
│  ├─ README.md
│  ├─ images/                 # 주요 화면 15장
│  ├─ videos/                 # 기능 검증 영상 13개
│  ├─ 01_overview.md
│  ├─ 02_architecture.md
│  ├─ 03_features.md
│  ├─ 04_data_flow.md
│  ├─ 05_validation.md
│  ├─ 06_project_scope.md
│  ├─ 07_project_structure.md
│  ├─ 08_operations.md
│  └─ 09_security_and_privacy.md
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
| `server/app/providers` | 외부 정보 Provider adapter |
| `server/tests` | Backend 회귀 |
| `web/src/app` | Next.js route |
| `web/src/components` | 화면과 사용자 상호작용 |
| `web/src/lib` | API client와 공통 로직 |
| `web/tests` | UI 계약 회귀 |
| `web/tests/e2e` | Browser E2E |
| `scripts` | 로컬 운영·Scheduler·검증 도구 |
| `docs/images` | 주요 기능 화면 |
| `docs/videos` | 실제 UI 기능 검증 영상 |

## 문서 구성

`01~07`은 다른 프로젝트와 동일한 핵심 문서 흐름을 사용하고, 이 프로젝트의 데이터·운영 특성 때문에 `08 Operations`, `09 Security & Privacy`를 추가했습니다.

```text
Overview
→ Architecture
→ Features
→ Data Flow
→ Validation
→ Project Scope
→ Project Structure
→ Operations
→ Security & Privacy
```

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

실제 투자 데이터, Secret과 런타임 산출물은 저장소 소스와 분리합니다.

## 소스 구성

저장소는 애플리케이션 소스, 테스트, 마이그레이션, 운영·검증 스크립트와 기술 문서로 구성합니다.

실제 투자 DB, 계정·보유정보, Secret과 로컬 런타임 산출물은 소스 관리 대상에 포함하지 않습니다.

---

[문서 목차](README.md) · [프로젝트 README](../README.md)
