# PocketPilot Backend

FastAPI backend foundation for PocketPilot.

## Safety
PocketPilot is **DEMO ONLY**. The server refuses to start if DEMO_ONLY is false. Never commit Pocket Option credentials, SSIDs, encryption keys, cookies, or tokens.

## Run locally
`python -m venv .venv` then `pip install -r requirements.txt` and `uvicorn app.main:app --reload`.

Endpoints: `GET /` and `GET /health`.

## Railway
Deploy as a Docker service and set `DEMO_ONLY=true`. Keep `POCKET_OPTION_SSID` and `ENCRYPTION_KEY` in Railway secrets.

BinaryOptionsTools-v2 / PyStrategy integration is the next implementation step after the base deployment is verified.
