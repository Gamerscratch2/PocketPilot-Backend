import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

SESSION_FILE = DATA_DIR / "session.enc"
SECRET_KEY_FILE = DATA_DIR / "secret.key"

APP_VERSION = "1.0.0"
SERVICE_NAME = "PocketPilot"


def get_port() -> int:
    return int(os.environ.get("PORT", "8000"))


def get_fernet():
    """Returns a Fernet cipher, deriving from ENCRYPTION_KEY or auto-generating one."""
    from cryptography.fernet import Fernet
    raw = os.environ.get("ENCRYPTION_KEY")
    if raw:
        try:
            return Fernet(raw.encode())
        except Exception:
            from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
            from cryptography.hazmat.primitives import hashes
            import base64
            kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32,
                             salt=b"pocketpilot-salt", iterations=200_000)
            return Fernet(base64.urlsafe_b64encode(kdf.derive(raw.encode())))
    if SECRET_KEY_FILE.exists():
        return Fernet(SECRET_KEY_FILE.read_bytes())
    k = Fernet.generate_key()
    SECRET_KEY_FILE.write_bytes(k)
    return Fernet(k)


# Real Pocket Option OTC asset symbols (metadata only — prices/payouts are fetched or null).
CURATED_ASSETS = [
    "EURUSD_otc", "GBPUSD_otc", "USDJPY_otc", "AUDUSD_otc", "USDCAD_otc",
    "USDCHF_otc", "EURJPY_otc", "EURGBP_otc", "NZDUSD_otc", "EURCAD_otc",
    "AUDCAD_otc", "AUDJPY_otc", "CADJPY_otc", "CHFJPY_otc", "EURCHF_otc",
    "GBPJPY_otc", "GBPCAD_otc", "BTCUSD_otc", "ETHUSD_otc", "LTCUSD_otc",
]


def ok(data):
    return {"success": True, "data": data}


def err(code, message, status=400):
    return {"success": False, "error": {"code": code, "message": message}, "_status": status}


def tf_to_seconds(tf: str) -> int:
    tf = (tf or "1m").strip().lower()
    units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    try:
        return int(tf[:-1]) * units.get(tf[-1], 60)
    except Exception:
        return 60
