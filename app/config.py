from functools import lru_cache
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    postgres_user: str = "techjobs"
    postgres_password: SecretStr
    postgres_db: str = "melbourne_tech_jobs"
    db_host: str = "db"
    db_port: int = 5432
    adzuna_app_id: SecretStr = SecretStr("")
    adzuna_app_key: SecretStr = SecretStr("")

    @property
    def database_url(self):
        return URL.create("postgresql+psycopg", username=self.postgres_user,
                          password=self.postgres_password.get_secret_value(),
                          host=self.db_host, port=self.db_port, database=self.postgres_db)


@lru_cache
def get_settings():
    return Settings()
