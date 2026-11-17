import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    token: str = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    admin_id: int = int(os.getenv("ADMIN_ID", "0"))
    db_path: str = os.getenv("DATABASE_PATH", "data/profit_ai.db")
    media_dir: str = os.getenv("MEDIA_DIR", "media")
    default_fee: float = float(os.getenv("DEFAULT_FEE_RESERVE", "0"))
    min_profit: float = float(os.getenv("MIN_PROFIT_RUB", "50"))
    currency: str = os.getenv("CURRENCY", "₽")

settings = Settings()
