from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str = "sqlite:///./nexora_brain.db"
    chunk_size: int = 1200
    chunk_overlap: int = 180
    model_config = SettingsConfigDict(env_file=".env", env_prefix="NEXORA_", extra="ignore")

@lru_cache
def get_settings() -> Settings:
    return Settings()
