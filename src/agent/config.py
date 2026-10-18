from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "my-agent"
    environment: str = "development"
    log_level: str = "INFO"
    groq_api_key: str = ""
    model:str="openai/gpt-oss-120b"
    temperature:int=0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
