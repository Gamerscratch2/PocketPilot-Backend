class StrategyEngine:
    async def evaluate(self, market_data: dict) -> dict:
        return {"signal": None, "reason": "No strategy configured yet"}
