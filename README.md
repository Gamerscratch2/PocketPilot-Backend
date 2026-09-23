# PocketPilot Backend

Backend foundation for PocketPilot.

## Current scope

- FastAPI API
- Railway/Docker deployment configuration
- `/` and `/health` endpoints
- Environment-based configuration
- Fernet encryption helpers
- DEMO-only safety configuration
- Initial abstractions for Pocket Option, market data, strategies, signals and risk
- Worker skeleton

## Safety

PocketPilot is designed to be DEMO ONLY. Do not place live-account credentials in this repository.

Secrets such as `POCKET_OPTION_SSID` and `ENCRYPTION_KEY` belong in Railway environment variables, not in Git.

## Local run

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload
```

Then open:

- http://127.0.0.1:8000/
- http://127.0.0.1:8000/health

## Railway

Deploy the repository as a Railway service. Railway should detect the Dockerfile automatically.

Set `DEMO_ONLY=true` in Railway variables.

The BinaryOptionsTools-v2 integration and PyStrategy worker are intentionally added in a later step after the base deployment is confirmed.
