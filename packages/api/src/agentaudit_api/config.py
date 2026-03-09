from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AGENTAUDIT_")

    database_url: str = "postgresql+psycopg2://agentaudit:agentaudit@localhost:5432/agentaudit"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = False


def get_settings() -> Settings:
    return Settings()
