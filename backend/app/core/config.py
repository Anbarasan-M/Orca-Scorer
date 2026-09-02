"""Application settings, loaded from environment variables / `.env`."""

from functools import lru_cache

from pydantic import PostgresDsn, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- PostgreSQL ---
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "orca_scorer"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = ""

    # --- App ---
    APP_NAME: str = "Orca Scorer API"
    DEBUG: bool = True
    SQL_ECHO: bool = False

    @computed_field
    @property
    def database_url(self) -> str:
        """SQLAlchemy URL. `postgresql+psycopg` selects the psycopg 3 driver."""
        return str(
            PostgresDsn.build(
                scheme="postgresql+psycopg",
                username=self.POSTGRES_USER,
                password=self.POSTGRES_PASSWORD,
                host=self.POSTGRES_HOST,
                port=self.POSTGRES_PORT,
                path=self.POSTGRES_DB,
            )
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
