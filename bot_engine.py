import asyncio
import time
from datetime import datetime, timezone

from strategy import generate_signal
from config import tf_to_seconds


class BotEngine:
    def __init__(self, service):
        self.service = service
        self.task = None
        self.status = "STOPPED"
        self.mode = "DEMO_AUTO"
        self.config = {}
        self.trades = 0
        self.wins = 0
        self.losses = 0
        self.profit = 0.0
        self.consecutive_losses = 0
        self.started_at = None
        self.stop_reason = None
        self.last_signal = None
        self._pause = asyncio.Event()
        self._stop = asyncio.Event()

    def start(self, config):
        if self.task and not self.task.done():
            return
        self.config = config or {}
        self.mode = self.config.get("mode", "DEMO_AUTO")
        self.status = "RUNNING"
        self.trades = self.wins = self.losses = 0
        self.profit = 0.0
        self.consecutive_losses = 0
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.stop_reason = None
        self._pause.clear()
        self._stop.clear()
        self.task = asyncio.create_task(self._loop())

    def stop(self, reason="manual"):
        self._stop.set()
        self.status = "STOPPED"
        self.stop_reason = reason

    def pause(self):
        self._pause.set()
        self.status = "PAUSED"

    def resume(self):
        self._pause.clear()
        self.status = "RUNNING"

    def snapshot(self):
        return {
            "status": self.status, "mode": self.mode,
            "tradesCount": self.trades, "wins": self.wins, "losses": self.losses,
            "profit": round(self.profit, 2), "startedAt": self.started_at,
            "asset": self.config.get("asset"), "timeframe": self.config.get("timeframe"),
            "stopReason": self.stop_reason, "lastSignal": self.last_signal,
        }

    async def _loop(self):
        asset = self.config.get("asset", "EURUSD_otc")
        timeframe = self.config.get("timeframe", "1m")
        amount = float(self.config.get("amount", 1))
        duration = int(self.config.get("duration", 60))
        min_score = int(self.config.get("minScore", 80))
        max_trades = int(self.config.get("maxTrades", 50))
        max_consec = 3
        period = max(tf_to_seconds(timeframe), 5)
        try:
            while not self._stop.is_set():
                await self._pause.wait()
                if self._stop.is_set():
                    break
                if not self.service.connected:
                    await asyncio.sleep(5)
                    continue
                if self.trades >= max_trades:
                    self.status = "STOPPED"
                    self.stop_reason = "max_trades_reached"
                    break
                if self.consecutive_losses >= max_consec:
                    self.status = "STOPPED"
                    self.stop_reason = "max_consecutive_losses"
                    break
                try:
                    res = await self.service.get_candles(asset, timeframe, 80)
                except Exception:
                    await asyncio.sleep(period)
                    continue
                if not res.get("success"):
                    await asyncio.sleep(period)
                    continue
                candles = res["data"]["candles"]
                sig = generate_signal(candles)
                self.last_signal = sig
                if sig["direction"] and sig["score"] >= min_score:
                    await self._execute(sig, asset, amount, duration, timeframe, period)
                await asyncio.sleep(max(period, 5))
        except asyncio.CancelledError:
            pass
        finally:
            if self.status not in ("STOPPED", "PAUSED"):
                self.status = "STOPPED"

    async def _execute(self, sig, asset, amount, duration, timeframe, period):
        direction = sig["direction"]
        client = self.service.client
        if self.mode == "SIGNALS_ONLY":
            self.trades += 1
            return
        if not client:
            return
        self.trades += 1
        try:
            if direction == "CALL":
                tid, _ = await asyncio.wait_for(
                    client.buy(asset=asset, amount=amount, time=duration), timeout=20)
            else:
                tid, _ = await asyncio.wait_for(
                    client.sell(asset=asset, amount=amount, time=duration), timeout=20)
            await asyncio.sleep(duration + 3)
            try:
                res = await asyncio.wait_for(client.check_win(tid), timeout=20)
            except Exception:
                res = {}
            result = ""
            profit = 0.0
            if isinstance(res, dict):
                result = str(res.get("result", "")).lower()
                profit = float(res.get("profit", 0) or 0)
            if result == "win":
                self.wins += 1
                self.consecutive_losses = 0
                self.profit += profit
            elif result == "loss":
                self.losses += 1
                self.consecutive_losses += 1
                self.profit += profit
        except Exception:
            pass
