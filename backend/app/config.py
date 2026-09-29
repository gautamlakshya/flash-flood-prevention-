from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Flash Flood Early Warning System"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # DB
    DATABASE_URL: str = "postgresql://user:password@db:5432/flashflood"
    
    # Redis
    REDIS_URL: str = "redis://redis:6379/0"
    
    # External APIs
    INSAT_API_KEY: str = ""
    IMD_API_KEY: str = ""
    DWR_API_KEY: str = ""
    MAP_STYLE_URL: str = "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json"
    
    # Mode
    DEMO_MODE: bool = True
    
    class Config:
        env_file = ".env"

settings = Settings()
