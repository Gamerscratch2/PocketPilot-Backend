from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import ok as _ok, err as _err, APP_VERSION, SERVICE_NAME
from pocket_service import PocketService
from bot_engine import BotEngine
from backtest_engine import run_backtest
from strategy import generate_signal

service = PocketService()
bot = BotEngine(service)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Auto-reconnect from an encrypted stored SSID, if present.
    stored = service._load_stored_ssid()
    if stored:
        try:
            await service.connect(stored)
        except Exception:
            pass
    yield


app = FastAPI(title="PocketPilot Backend", version=APP_VERSION, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def respond(env: dict):
    status = 200 if env.get("success") else env.pop("_status", 400)
    env.pop("_status", None)
    return JSONResponse(content=env, status_code=status)


@app.get("/")
def root():
    return {"service": SERVICE_NAME, "status": "online", "version": APP_VERSION, "demo_only": True}


@app.get("/health")
def health():
    return {"status": "ok", "service": SERVICE_NAME, "demo_only": True, "version": APP_VERSION}


@app.get("/status")
async def status():
    return respond(await service.status())


@app.get("/assets")
async def assets():
    return respond(await service.get_assets())


@app.get("/candles")
async def candles(request: Request):
    q = request.query_params
    return respond(await service.get_candles(q.get("asset", "EURUSD_otc"),
                                             q.get("timeframe", "1m"),
                                             q.get("amount", 100)))


@app.get("/server-time")
async def server_time():
    return respond(await service.get_server_time())


@app.get("/system-check")
async def system_check():
    return respond(await service.system_check())


@app.post("/auth/connect-ssid")
async def connect_ssid(request: Request):
    body = await request.json()
    return respond(await service.connect(body.get("ssid", "")))


@app.post("/auth/login-browser")
async def login_browser(request: Request):
    body = await request.json()
    return respond(await service.login_browser_start(body.get("email"), body.get("password"),
                                                      body.get("demo", True)))


@app.get("/auth/login-browser/status")
async def login_browser_status(request: Request):
    q = request.query_params
    return respond(await service.login_browser_status(q.get("jobId")))


@app.post("/auth/validate")
async def validate():
    return respond(await service.validate())


@app.post("/auth/reconnect")
async def reconnect():
    return respond(await service.reconnect())


@app.post("/auth/disconnect")
async def disconnect():
    bot.stop("disconnect")
    return respond(await service.disconnect())


@app.post("/trade/manual")
async def trade_manual(request: Request):
    body = await request.json()
    return respond(await service.trade_manual(body.get("asset"), body.get("direction"),
                                             body.get("amount"), body.get("duration", 60)))


@app.post("/bot/start")
async def bot_start(request: Request):
    body = await request.json()
    config = body.get("config", {}) or {}
    if not service.connected:
        return respond(_err("NOT_CONNECTED", "Session Pocket Option non connectée.", 409))
    bot.start(config)
    return respond(_ok({"status": bot.status, "startedAt": bot.started_at, "config": config}))


@app.post("/bot/stop")
async def bot_stop():
    bot.stop("manual")
    return respond(_ok({"status": bot.status}))


@app.post("/bot/pause")
async def bot_pause():
    bot.pause()
    return respond(_ok({"status": bot.status}))


@app.post("/bot/resume")
async def bot_resume():
    bot.resume()
    return respond(_ok({"status": bot.status}))


@app.get("/bot/status")
async def bot_status():
    return respond(_ok(bot.snapshot()))


@app.post("/emergency-stop")
async def emergency_stop():
    bot.stop("EMERGENCY_STOP")
    if service.connected:
        await service.disconnect()
    return respond(_ok({"stopped": True, "status": bot.status, "reason": "EMERGENCY_STOP"}))


@app.post("/backtest/run")
async def backtest_run(request: Request):
    body = await request.json()
    config = body.get("config", {}) or {}
    asset = config.get("asset", "EURUSD_otc")
    timeframe = config.get("timeframe", "1m")
    amount_candles = int(config.get("candles", 300))
    if not service.connected:
        return respond(_err("NOT_CONNECTED", "Session non connectée pour récupérer l'historique.", 409))
    res = await service.get_candles(asset, timeframe, amount_candles)
    if not res.get("success"):
        return respond(res)
    candles = res["data"]["candles"]
    result = run_backtest(candles, config)
    result.update({"asset": asset, "timeframe": timeframe, "candlesUsed": len(candles),
                   "status": "COMPLETED"})
    return respond(_ok(result))


@app.post("/analyse/signal")
async def analyse_signal(request: Request):
    body = await request.json()
    asset = body.get("asset", "EURUSD_otc")
    timeframe = body.get("timeframe", "1m")
    res = await service.get_candles(asset, timeframe, 100)
    if not res.get("success"):
        return respond(res)
    sig = generate_signal(res["data"]["candles"])
    return respond(_ok({"asset": asset, "timeframe": timeframe, "signal": sig,
                        "computedAt": datetime.now(timezone.utc).isoformat()}))
