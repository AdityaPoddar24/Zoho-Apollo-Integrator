from functools import lru_cache
from pydantic import BaseSettings, Field

class Settings(BaseSettings):
    apollo_api_key: str = Field(..., env="APOLLO_API_KEY")
    mysql_uri:     str = Field(..., env="MYSQL_URI")
    redis_url:     str = Field(..., env="REDIS_URL")
    # Zoho creds kept for the later push-back phase
    zoho_client_id: str = Field("", env="ZOHO_CLIENT_ID")
    zoho_client_secret: str = Field("", env="ZOHO_CLIENT_SECRET")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

@lru_cache
def get_settings() -> Settings:
    return Settings()
