from pydantic_settings import BaseSettings
from pydantic import HttpUrl

class AppConfig(BaseSettings):
    telegram_bot_token: str
    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_bucket: str = "qa-pipeline"
    minio_secure: bool = False
    llm_provider: str = "cloud"
    gemini_api_key: str | None = None
    cloud_model_name: str = "gemini-pro"
    local_llm_endpoint: HttpUrl | None = "http://localhost:8000/v1"
    local_model_name: str = "llama2"
    gemini_temperature: float = 0.7

    class Config:
        env_file = ".env"
        extra = "ignore"

config = AppConfig()
