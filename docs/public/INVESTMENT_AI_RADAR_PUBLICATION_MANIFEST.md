# 공개 파일 Manifest

## 공개 포함

- `README.md`
- `server/app/`
- `server/tests/`
- `server/alembic/`
- `web/src/`
- `web/tests/`
- `scripts/`
- `.env.example`
- `.gitignore`
- `docs/*.md`
- `docs/public/*.md`
- `docs/demo/*.md`
- `docs/validation/*.md`
- `docs/images/*.png`
- `docs/videos/*.mp4`

## 공개 제외

- 실제 투자 DB
- `.env`, `.env.local`
- 개인 계정·보유정보 export
- credentials·private configuration
- 개인 Windows 절대경로가 포함된 내부 운영 문서

## 로컬 전용

- `.local/`
- `*.db`, `*.sqlite*`
- `logs/`
- `temp/`
- `backup/`
- `.next/`
- `node_modules/`
- `.venv/`
- test·lint·coverage cache

## 공개 전 확인 기준

1. `git status`와 `git ls-files`로 추적 대상을 확인합니다.
2. `.local`, DB, 환경파일이 ignore되는지 재확인합니다.
3. Secret·privacy 문자열을 검색합니다.
4. Markdown 링크와 미디어 경로를 확인합니다.
5. 전체 최종 QA를 실행합니다.
6. 사용자 확인 후 Git 쓰기와 remote push를 수행합니다.

## 최종 공개 상태

공개용 소스·문서·이미지·영상 구성과 민감파일 제외 검사를 완료한 상태를 최종 기준으로 사용합니다.

---

[문서 목차](../README.md) · [프로젝트 README](../../README.md)
