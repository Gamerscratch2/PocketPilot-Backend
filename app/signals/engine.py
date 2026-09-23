class SignalEngine:
    async def generate(self, market_data: dict, strategy_result: dict) -> dict:
        return {"action":"NO_TRADE","confidence":0.0,"reason":"Signal engine not configured yet"}
