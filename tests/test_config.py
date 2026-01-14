import os
from unittest import mock
from pydantic import ValidationError, HttpUrl
import pytest
from pydantic_settings import BaseSettings

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
        extra = "ignore"

def test_config_loads_from_env():
    with mock.patch.dict(os.environ, {
        "TELEGRAM_BOT_TOKEN": "test_token",
        "MINIO_ENDPOINT": "localhost:9000",
        "MINIO_ACCESS_KEY": "minioadmin",
        "MINIO_SECRET_KEY": "minioadmin",
    }):
        config = AppConfig()
        assert config.telegram_bot_token == "test_token"
        assert config.minio_endpoint == "localhost:9000"
        assert config.minio_access_key == "minioadmin"
        assert config.minio_secret_key == "minioadmin"

def test_config_default_values():
    with mock.patch.dict(os.environ, {
        "TELEGRAM_BOT_TOKEN": "test_token",
        "MINIO_ENDPOINT": "localhost:9000",
        "MINIO_ACCESS_KEY": "minioadmin",
        "MINIO_SECRET_KEY": "minioadmin",
        "LLM_PROVIDER": "cloud", # Explicitly set for this test
    }):
        config = AppConfig()
        assert config.minio_bucket == "qa-pipeline"
        assert config.minio_secure is False
        assert config.llm_provider == "cloud"
        assert config.gemini_temperature == 0.7

def test_config_missing_required_env_var():
    with mock.patch.dict(os.environ, clear=True):
        with pytest.raises(ValidationError):
            AppConfig()
