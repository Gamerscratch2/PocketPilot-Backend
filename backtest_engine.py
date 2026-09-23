from strategy import generate_signal


def run_backtest(candles, config):
    """Run the EMA/RSI strategy over real historical candles.

    A position opened at close[i] is resolved at close[i + steps] using price
    movement (CALL wins if exit > entry, PUT wins if exit < entry).
    """
    amount = float(config.get("amount", 1))
    payout = float(config.get("payout", 0.85))
    steps = max(1, int(config.get("durationSteps", 1)))

    closes = [c["close"] for c in candles if c.get("close") is not None]
    n = len(closes)
    if n < 30:
        return {"tradesCount": 0, "wins": 0, "losses": 0, "winrate": 0,
                "profit": 0, "drawdown": 0, "profitFactor": 0,
                "maxConsecutiveWins": 0, "maxConsecutiveLosses": 0,
                "equityCurve": [0.0]}

    equity = [0.0]
    peak = 0.0
    max_dd = 0.0
    wins = losses = 0
    gross_profit = 0.0
    gross_loss = 0.0
    cons_w = cons_l = 0
    max_cw = max_cl = 0
    open_pos = None

    for i in range(25, n - steps):
        if open_pos is None:
            window = candles[: i + 1]
            sig = generate_signal(window)
            if sig["direction"] and sig["score"] >= int(config.get("minScore", 75)):
                open_pos = {"direction": sig["direction"], "entry": closes[i], "i": i}
        else:
            exit_price = closes[i]
            entry = open_pos["entry"]
            won = (open_pos["direction"] == "CALL" and exit_price > entry) or \
                  (open_pos["direction"] == "PUT" and exit_price < entry)
            pnl = amount * payout if won else -amount
            equity.append(round(equity[-1] + pnl, 4))
            peak = max(peak, equity[-1])
            max_dd = max(max_dd, (peak - equity[-1]))
            if won:
                wins += 1
                cons_w += 1
                cons_l = 0
                gross_profit += pnl
                max_cw = max(max_cw, cons_w)
            else:
                losses += 1
                cons_l += 1
                cons_w = 0
                gross_loss += abs(pnl)
                max_cl = max(max_cl, cons_l)
            open_pos = None

    total = wins + losses
    winrate = round((wins / total) * 100, 2) if total else 0
    profit = round(equity[-1], 2)
    profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else (float("inf") if gross_profit > 0 else 0)
    return {
        "tradesCount": total,
        "wins": wins,
        "losses": losses,
        "winrate": winrate,
        "profit": profit,
        "drawdown": round(max_dd, 2),
        "profitFactor": profit_factor if profit_factor != float("inf") else 99.0,
        "maxConsecutiveWins": max_cw,
        "maxConsecutiveLosses": max_cl,
        "equityCurve": equity,
    }
