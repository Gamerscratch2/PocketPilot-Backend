import asyncio
from app.config import settings

async def main():
    if not settings.demo_only:
        raise RuntimeError("Worker refuses to start outside DEMO mode.")
    while True:
        await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())
