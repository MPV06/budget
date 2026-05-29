from typing import Literal
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    plaid_client_id: str = Field(min_length=1)
    plaid_secret: str = Field(min_length=1)
    plaid_env: Literal["sandbox", "development", "production"]
    plaid_access_token: str = ""
    paycheck_net_amount: float = Field(gt=0)
    db_path: str = "./data/budget.db"
    # If set, use this Postgres connection string (e.g., Supabase).
    # When empty, falls back to SQLite at db_path.
    database_url: str = ""


def get_settings() -> Settings:
    return Settings()
