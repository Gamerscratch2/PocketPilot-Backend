import asyncio
import re
import time
import uuid
from datetime import datetime, timezone

from config import (ok as _ok, err as _err, get_fernet, SESSION_FILE,
                    CURATED_ASSETS, APP_VERSION, tf_to_seconds, SERVICE_NAME)


def _norm_candle(c):
    try:
        return {
            "timestamp": c.get("time"),
            "time": c.get("time"),
            "open": float(c["open"]),
            "high": float(c["high"]),
            "low": float(c["low"]),
            "close": float(c["close"]),
            "volume": c.get("volume"),
        }
    except Exception:
        return None


class PocketService:
    def __init__(self):
        self.client = None
        self.ssid = None
        self.is_demo = False
        self.connected = False
        self.balance = None
        self.currency = "USD"
        self.last_error = None
        self.reconnect_count = 0
        self.last_validated = None
        self._lock = asyncio.Lock()
        self._login_jobs = {}

    # ---------- SSID / encryption ----------
    def _parse_is_demo(self, ssid):
        m = re.search(r'"is_?[Dd]emo"\s*:\s*(\d|true|false)', ssid or "", re.IGNORECASE)
        if not m:
            return None
        return m.group(1).lower() in ("1", "true")

    def _load_stored_ssid(self):
        if SESSION_FILE.exists():
            try:
                return get_fernet().decrypt(SESSION_FILE.read_bytes()).decode()
            except Exception:
                return None
        return None

    def _store_ssid(self, ssid):
        try:
            get_fernet().encrypt(ssid.encode())  # validate key works
            SESSION_FILE.write_bytes(get_fernet().encrypt(ssid.encode()))
        except Exception as e:
            self.last_error = f"échec chiffrement SSID: {e}"

    def _clear_stored(self):
        try:
            if SESSION_FILE.exists():
                SESSION_FILE.unlink()
        except Exception:
            pass

    # ---------- connection ----------
    async def _make_client(self, ssid):
        from BinaryOptionsToolsV2.pocketoption import PocketOptionAsync
        return PocketOptionAsync(ssid=ssid)

    async def connect(self, ssid):
        async with self._lock:
            if not ssid:
                return _err("BAD_SSID", "SSID vide.")
            demo_flag = self._parse_is_demo(ssid)
            if demo_flag is False:
                return _err("REAL_ACCOUNT_BLOCKED", "Compte réel détecté. PocketPilot n'accepte que les comptes DEMO.", 403)
            try:
                client = await self._make_client(ssid)
                bal = await asyncio.wait_for(client.balance(), timeout=25)
                acct = getattr(client, "account_type", None)
                if acct is not None and str(acct).lower() in ("real", "0", "false"):
                    self.connected = False
                    return _err("REAL_ACCOUNT_BLOCKED", "Compte réel détecté après connexion. DEMO uniquement.", 403)
                self.client = client
                self.ssid = ssid
                self.is_demo = True
                self.connected = True
                self.balance = float(bal) if bal is not None else None
                self.last_error = None
                self.last_validated = datetime.now(timezone.utc).isoformat()
                self.reconnect_count = 0
                self._store_ssid(ssid)
                return _ok({"isDemo": True, "balance": self.balance, "currency": self.currency,
                            "accountType": "DEMO", "connected": True,
                            "lastValidatedAt": self.last_validated})
            except Exception as e:
                self.connected = False
                self.last_error = str(e)
                return _err("CONNECT_FAILED", f"Échec de connexion Pocket Option: {e}", 502)

    async def validate(self):
        if not self.client:
            return _err("NOT_CONNECTED", "Aucune session active.", 409)
        try:
            t0 = time.time()
            bal = await asyncio.wait_for(self.client.balance(), timeout=20)
            self.balance = float(bal) if bal is not None else None
            self.connected = True
            self.last_validated = datetime.now(timezone.utc).isoformat()
            return _ok({"isDemo": True, "balance": self.balance,
                        "latencyMs": int((time.time() - t0) * 1000)})
        except Exception as e:
            self.connected = False
            self.last_error = str(e)
            return _err("VALIDATE_FAILED", str(e), 502)

    async def reconnect(self):
        ssid = self.ssid or self._load_stored_ssid()
        if not ssid:
            return _err("NO_STORED_SSID", "Aucun SSID stocké pour la reconnexion.", 409)
        self.reconnect_count += 1
        return await self.connect(ssid)

    async def disconnect(self):
        async with self._lock:
            self.connected = False
            self.client = None
            self.ssid = None
            self.balance = None
            self._clear_stored()
            return _ok({"connected": False})

    # ---------- status ----------
    async def status(self):
        latency = None
        if self.connected and self.client:
            try:
                t0 = time.time()
                bal = await asyncio.wait_for(self.client.balance(), timeout=15)
                self.balance = float(bal) if bal is not None else None
                latency = int((time.time() - t0) * 1000)
                self.last_validated = datetime.now(timezone.utc).isoformat()
            except Exception as e:
                self.connected = False
                self.last_error = str(e)
        return _ok({
            "connected": self.connected,
            "isDemo": self.is_demo if self.connected else False,
            "balance": self.balance,
            "currency": self.currency,
            "accountType": "DEMO" if self.is_demo else "UNKNOWN",
            "serverTime": datetime.now(timezone.utc).isoformat(),
            "latencyMs": latency,
            "lastValidatedAt": self.last_validated,
            "lastError": self.last_error,
            "reconnectCount": self.reconnect_count,
        })

    # ---------- market data ----------
    async def get_candles(self, asset, timeframe, amount=100):
        if not self.connected or not self.client:
            return _err("NOT_CONNECTED", "Session Pocket Option non connectée.", 409)
        period = tf_to_seconds(timeframe)
        amount = max(10, min(int(amount or 100), 500))
        hours = max(0.2, (amount * period) / 3600 * 1.6 + 0.1)
        try:
            agen = self.client.get_candles_live(asset, period=period, hours=hours, max_rows=amount)
            try:
                closed, _forming = await asyncio.wait_for(agen.__anext__(), timeout=25)
            finally:
                await agen.aclose()
            candles = [c for c in (_norm_candle(c) for c in (closed or [])) if c]
            candles = candles[-amount:]
            if not candles:
                return _err("NO_CANDLES", "Aucun chandelier reçu de Pocket Option.", 502)
            return _ok({"candles": candles, "asset": asset, "timeframe": timeframe})
        except asyncio.TimeoutError:
            return _err("CANDLES_TIMEOUT", "Délai dépassé pour la réception des chandeliers.", 504)
        except Exception as e:
            self.last_error = str(e)
            return _err("CANDLES_FAILED", str(e), 502)

    async def get_assets(self):
        assets = []
        if self.connected and self.client:
            for method in ("get_assets", "assets"):
                fn = getattr(self.client, method, None)
                if fn:
                    try:
                        res = await asyncio.wait_for(fn(), timeout=20) if asyncio.iscoroutinefunction(fn) else fn()
                        if isinstance(res, dict):
                            for name, info in res.items():
                                info = info or {}
                                assets.append({"name": name, "symbol": name,
                                               "open": bool(info.get("open", info.get("enabled", True))),
                                               "payout": info.get("payout"),
                                               "price": info.get("price")})
                            break
                        elif isinstance(res, list):
                            for a in res:
                                name = a.get("name") or a.get("symbol") if isinstance(a, dict) else str(a)
                                assets.append({"name": name, "symbol": name,
                                               "open": True, "payout": None, "price": None})
                            break
                    except Exception:
                        assets = []
        if not assets:
            assets = [{"name": a, "symbol": a, "open": True, "payout": None, "price": None}
                      for a in CURATED_ASSETS]
        return _ok(assets)

    async def get_server_time(self):
        return _ok({"serverTime": datetime.now(timezone.utc).isoformat(),
                    "utcTime": datetime.now(timezone.utc).isoformat()})

    # ---------- trading ----------
    async def trade_manual(self, asset, direction, amount, duration):
        if not self.connected or not self.client:
            return _err("NOT_CONNECTED", "Session non connectée — trade refusé.", 409)
        if not self.is_demo:
            return _err("REAL_ACCOUNT_BLOCKED", "Compte réel détecté — trade bloqué.", 403)
        direction = (direction or "").upper()
        if direction not in ("CALL", "PUT"):
            return _err("BAD_DIRECTION", "direction doit être CALL ou PUT.", 400)
        try:
            amount = float(amount)
            duration = int(duration or 60)
            if direction == "CALL":
                tid, deal = await asyncio.wait_for(
                    self.client.buy(asset=asset, amount=amount, time=duration), timeout=20)
            else:
                tid, deal = await asyncio.wait_for(
                    self.client.sell(asset=asset, amount=amount, time=duration), timeout=20)
            deal = deal or {}
            entry_price = None
            for k in ("price", "open_price", "entry_price", "strike"):
                if deal.get(k) is not None:
                    entry_price = deal.get(k)
                    break
            return _ok({"trade": {
                "id": str(tid),
                "asset": asset, "direction": direction,
                "amount": amount, "duration": duration,
                "entryPrice": entry_price,
                "openedAt": datetime.now(timezone.utc).isoformat(),
                "status": "OPEN",
            }})
        except Exception as e:
            self.last_error = str(e)
            return _err("TRADE_FAILED", str(e), 502)

    # ---------- system ----------
    async def system_check(self):
        comps = []
        ready = True
        # Python
        import sys
        comps.append({"name": "Python", "ok": True, "detail": sys.version.split()[0]})
        # BinaryOptionsToolsV2
        try:
            import BinaryOptionsToolsV2  # noqa
            comps.append({"name": "BinaryOptionsToolsV2", "ok": True, "detail": "installé"})
        except Exception as e:
            comps.append({"name": "BinaryOptionsToolsV2", "ok": False, "detail": str(e)})
            ready = False
        # Playwright (optional)
        try:
            import playwright  # noqa
            comps.append({"name": "Playwright", "ok": True, "detail": "installé (login navigateur possible)"})
        except Exception:
            comps.append({"name": "Playwright", "ok": False, "detail": "non installé (login navigateur désactivé — utilisez le SSID)"})
        # Chromium launch test (real)
        try:
            from playwright.async_api import async_playwright as _apw
            async def _test_launch():
                async with _apw() as _p:
                    _b = await _p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage", "--disable-gpu", "--no-zygote", "--disable-blink-features=AutomationControlled"])
                    await _b.close()
            await _test_launch()
            comps.append({"name": "Chromium Launch", "ok": True, "detail": "lancement OK"})
        except Exception as e:
            comps.append({"name": "Chromium Launch", "ok": False, "detail": str(e)[:300]})
        # Session
        comps.append({"name": "Session Pocket Option", "ok": self.connected,
                      "detail": "connecté" if self.connected else "non connecté"})
        # Encryption
        try:
            get_fernet()
            comps.append({"name": "Chiffrement SSID", "ok": True, "detail": "clé disponible"})
        except Exception as e:
            comps.append({"name": "Chiffrement SSID", "ok": False, "detail": str(e)})
            ready = False
        return _ok({"ready": ready and self.connected, "components": comps,
                    "demoOnly": True, "version": APP_VERSION})

    # ---------- login browser (async job) ----------
    async def login_browser_start(self, email, password, demo=True):
        if not email or not password:
            return _err("BAD_CREDENTIALS", "email et password requis.", 400)
        job_id = str(uuid.uuid4())
        self._login_jobs[job_id] = {"status": "running", "result": None}
        asyncio.create_task(self._login_browser_task(job_id, email, password, demo))
        return _ok({"jobId": job_id, "status": "running"})

    async def _login_browser_task(self, job_id, email, password, demo):
        try:
            result = await self._login_browser_impl(email, password, demo)
            self._login_jobs[job_id] = {"status": "done", "result": result}
        except Exception as e:
            self._login_jobs[job_id] = {"status": "error", "result": str(e)}

    async def login_browser_status(self, job_id):
        job = self._login_jobs.get(job_id)
        if not job:
            return _err("JOB_NOT_FOUND", "Job introuvable.", 404)
        return _ok({"jobId": job_id, "status": job["status"], "result": job["result"]})

    async def _login_browser_impl(self, email, password, demo=True):
        try:
            from playwright.async_api import async_playwright
        except Exception:
            return _err("PLAYWRIGHT_MISSING",
                        "Playwright n'est pas installé sur ce déploiement.", 501)
        if not email or not password:
            return _err("BAD_CREDENTIALS", "email et password requis.", 400)

        captured = {"ssid": None}
        found = asyncio.Event()

        def _check_frame(data):
            if captured["ssid"]:
                return
            if isinstance(data, str) and '"auth"' in data and '"isDemo"' in data:
                captured["ssid"] = data.strip()
                found.set()

        async def _do_login():
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage", "--disable-gpu", "--no-zygote", "--disable-blink-features=AutomationControlled"]
                )
                try:
                    context = await browser.new_context(
                        viewport={"width": 1280, "height": 800},
                        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    )
                    page = await context.new_page()

                    def _on_ws(ws):
                        ws.on("framereceived", lambda payload: _check_frame(payload))
                        ws.on("framesent", lambda payload: _check_frame(payload))
                    page.on("websocket", _on_ws)

                    try:
                        await page.goto("https://pocketoption.com/login", timeout=25000, wait_until="domcontentloaded")
                    except Exception:
                        pass  # Le goto peut timeout (anti-bot/redirect) — on vérifie le formulaire ensuite

                    # Wait for the login form to appear
                    await page.wait_for_selector('input[type="email"]', timeout=12000)
                    email_selectors = ['input[type="email"]', 'input[name="email"]', 'input[placeholder*="mail" i]']
                    pwd_selectors = ['input[type="password"]', 'input[name="password"]']

                    filled_email = False
                    for sel in email_selectors:
                        try:
                            el = page.locator(sel).first
                            if await el.count() and await el.is_visible():
                                await el.fill(email, timeout=3000)
                                filled_email = True
                                break
                        except Exception:
                            continue
                    if not filled_email:
                        raise RuntimeError("Champ email introuvable sur la page de connexion.")

                    filled_pwd = False
                    for sel in pwd_selectors:
                        try:
                            el = page.locator(sel).first
                            if await el.count() and await el.is_visible():
                                await el.fill(password, timeout=3000)
                                filled_pwd = True
                                break
                        except Exception:
                            continue
                    if not filled_pwd:
                        raise RuntimeError("Champ mot de passe introuvable.")

                    submitted = False
                    for sel in ['button[type="submit"]', 'button:has-text("Sign in")', 'button:has-text("Login")', 'button:has-text("Se connecter")']:
                        try:
                            el = page.locator(sel).first
                            if await el.count() and await el.is_enabled():
                                await el.click(timeout=3000)
                                submitted = True
                                break
                        except Exception:
                            continue
                    if not submitted:
                        raise RuntimeError("Bouton de connexion introuvable.")

                    try:
                        await asyncio.wait_for(found.wait(), timeout=12)
                    except asyncio.TimeoutError:
                        raise RuntimeError("SSID non capturé après login. Vérifiez vos identifiants ou utilisez le SSID manuel.")

                    return captured["ssid"]
                finally:
                    await browser.close()

        try:
            ssid = await asyncio.wait_for(_do_login(), timeout=25)
            return await self.connect(ssid)
        except asyncio.TimeoutError:
            return _err("LOGIN_TIMEOUT", "Délai dépassé — connexion trop lente. Utilisez le SSID manuel.", 504)
        except RuntimeError as e:
            msg = str(e)
            code = "LOGIN_FORM_NOT_FOUND" if "introuvable" in msg else "LOGIN_FAILED"
            return _err(code, msg, 502)
        except Exception as e:
            self.last_error = str(e)
            return _err("LOGIN_BROWSER_FAILED", str(e), 502)
