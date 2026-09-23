from app.config import settings

class PocketOptionClient:
    """DEMO-only adapter; BinaryOptionsTools-v2 is connected in the next integration step."""
    def __init__(self):
        if not settings.demo_only:
            raise RuntimeError("Live trading is disabled.")
        self.connected = False
    async def connect(self):
        if not settings.demo_only:
            raise RuntimeError("Live trading is disabled.")
        self.connected = True
    async def disconnect(self):
        self.connected = False
