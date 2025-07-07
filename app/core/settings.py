from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import Field, Extra

class Settings(BaseSettings):
    apollo_api_key:        str = Field(..., env="APOLLO_API_KEY")
    mysql_uri:             str = Field(..., env="MYSQL_URI")
    redis_url:             str = Field(..., env="REDIS_URL")
    zoho_client_id:        str = Field("",  env="ZOHO_CLIENT_ID")
    zoho_client_secret:    str = Field("",  env="ZOHO_CLIENT_SECRET")
    public_base_url:       str | None = Field(None, env="PUBLIC_BASE_URL")
    apollo_webhook_secret: str | None = Field(None, env="APOLLO_WEBHOOK_SECRET")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        # you can still forbid _other_ extras:
        extra = Extra.forbid

@lru_cache
def get_settings() -> Settings:
    return Settings()