# Investment AI Radar Server

Python 3.12 기반 최소 FastAPI 기준본입니다. 현재 제공 API는 `/health`와
`/api/v1/system/info`뿐이며 시장 데이터나 추천을 생성하지 않습니다.

```powershell
py -V:3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```
