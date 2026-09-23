from fastapi import FastAPI
from app.config import settings
from app.api.health import router as health_router

app = FastAPI(title="PocketPilot Backend", version="0.1.0")
app.include_router(health_router)

@app.get("/")
async def root():
    return {"service":"PocketPilot","status":"online","version":"0.1.0","demo_only":settings.demo_only}
