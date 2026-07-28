from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Sajilo Loan API"
    app_env: str = "development"
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db: str = "sajilo_loan"
    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "sajilo-loan-api"
    jwt_audience: str = "sajilo-loan-users"
    access_token_expire_minutes: int = 60
    # Default bank-defined Personal Loan annual interest rate (percent). This is
    # the seeded fallback; the live value can be overridden at runtime and is
    # stored in the app_settings collection (see loan_settings_service).
    personal_loan_interest_rate: float = 11.0
    upload_dir: str = "uploads"
    max_upload_bytes: int = 10 * 1024 * 1024
    cors_allowed_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    auth_rate_limit_count: int = 10
    auth_rate_limit_window_seconds: int = 60
    expensive_rate_limit_count: int = 20
    expensive_rate_limit_window_seconds: int = 60
    tesseract_cmd: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_security_settings(self) -> "Settings":
        is_development = self.app_env.lower() == "development"
        weak_secret = self.jwt_secret_key in {"change-me", "changeme", "secret"}
        if not is_development and (weak_secret or len(self.jwt_secret_key) < 32):
            raise ValueError(
                "JWT_SECRET_KEY must be set to a strong secret outside development."
            )

        if self.max_upload_bytes <= 0:
            raise ValueError("MAX_UPLOAD_BYTES must be greater than 0.")

        return self

    @property
    def parsed_cors_allowed_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.cors_allowed_origins.split(",")
            if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
