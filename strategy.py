from indicators import ema_series, rsi


def generate_signal(candles):
    """Build a directional signal from a list of real candle dicts.

    Returns: { direction: "CALL"|"PUT"|None, score, indicators, trend, reason }
    """
    closes = [float(c["close"]) for c in candles if c.get("close") is not None]
    if len(closes) < 25:
        return {"direction": None, "score": 0, "indicators": {}, "reason": "pas assez de données"}

    e9 = ema_series(closes, 9)
    e21 = ema_series(closes, 21)
    rsi_val = rsi(closes, 14)

    if None in (e9[-1], e21[-1], e9[-2], e21[-2]):
        return {"direction": None, "score": 0, "indicators": {"rsi": round(rsi_val, 2)}}

    le9, le21, pe9, pe21 = e9[-1], e21[-1], e9[-2], e21[-2]
    crossed_up = pe9 <= pe21 and le9 > le21
    crossed_down = pe9 >= pe21 and le9 < le21

    direction, score = None, 50
    if crossed_up and rsi_val > 50:
        direction = "CALL"
        score = min(100, int(50 + (rsi_val - 50)))
    elif crossed_down and rsi_val < 50:
        direction = "PUT"
        score = min(100, int(50 + (50 - rsi_val)))

    return {
        "direction": direction,
        "score": score,
        "indicators": {"ema9": round(le9, 5), "ema21": round(le21, 5), "rsi": round(rsi_val, 2)},
        "trend": "haussière" if le9 > le21 else "baissière",
        "reason": "croisement EMA9/EMA21 confirmé par RSI" if direction else "aucun croisement confirmé",
    }
