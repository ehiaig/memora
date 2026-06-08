from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Memora"
    app_version: str = "0.1.0"
    api_v1_prefix: str = "/api/v1"

    database_url: str
    openai_api_key: str
    embedding_model_name: str
    embedding_dimensions: int = 1536

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


settings = Settings()
