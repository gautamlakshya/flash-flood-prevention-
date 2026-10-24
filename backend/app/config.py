from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "Flash Flood Early Warning System"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    ENV: str = "development"
    CORS_ORIGINS: str = ""

    # DB
    DATABASE_URL: str = "postgresql://user:password@db:5432/flashflood"

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"

    # External APIs
    INSAT_API_KEY: str = ""
    IMD_API_KEY: str = ""
    DWR_API_KEY: str = ""
    MAP_STYLE_URL: str = "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json"

    # Open-Meteo Rainfall Provider (Chungthang Basin)
    OPEN_METEO_API_URL: str = "https://api.open-meteo.com/v1/forecast"
    OPEN_METEO_LATITUDE: float = 27.6033
    OPEN_METEO_LONGITUDE: float = 88.6475
    OPEN_METEO_TIMEOUT_SECONDS: int = 10
    RAINFALL_STALE_THRESHOLD_MINUTES: int = 180

    # Web Push Notification Settings (PWA Standards-Based Push)
    VAPID_PUBLIC_KEY: str = ""
    VAPID_PRIVATE_KEY: str = ""
    VAPID_CLAIM_EMAIL: str = "mailto:alerts@chungthang-ffews.gov.in"
    WEB_PUSH_ENABLED: bool = True

    # SMS Channel Settings (Architectural Interface - Non-Configured by Default)
    SMS_ENABLED: bool = False
    SMS_GATEWAY_URL: str = ""
    SMS_ENTITY_ID: str = ""
    SMS_SENDER_ID: str = ""

    # Security & Administration
    ALERT_ADMIN_KEY: str = ""
    ALERT_COOLDOWN_MINUTES: int = 60

    # Ingestion Cron Authentication Secret
    INGESTION_CRON_SECRET: str = ""

    # Mode
    DEMO_MODE: bool = True

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
