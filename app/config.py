from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_env: str = "production"
    demo_only: bool = True
    pocket_option_ssid: str | None = None
    encryption_key: str | None = None
    log_level: str = "INFO"
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore")

settings = Settings()
if not settings.demo_only:
    raise RuntimeError("PocketPilot is DEMO ONLY. DEMO_ONLY must remain true.")
