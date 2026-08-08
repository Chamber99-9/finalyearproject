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
    access_token_expire_minutes: int = 720
    # Default bank-defined Personal Loan annual interest rate (percent). This is
    # the seeded fallback; the live value can be overridden at runtime and is
    # stored in the app_settings collection (see loan_settings_service).
    personal_loan_interest_rate: float = 11.0
    # Base lending rate (percent). Effective rate = base + loan-type spread +
    # tenure adjustment (see loan_rate_service). Admin-overridable at runtime.
    base_lending_rate: float = 8.0
    # Loan repayment: EMI is due on this day each month; a user is blacklisted
    # after this many consecutive missed installments.
    emi_due_day: int = 10
    blacklist_overdue_months: int = 3
    # EMI can be paid only within this many days before the due date (or after,
    # if overdue) — not arbitrarily early.
    emi_payment_window_days: int = 7
    # Email reminder is sent this many days before the EMI due date.
    reminder_days_before: int = 7
    # Background scheduler: automatically emails EMI reminders on an interval so
    # customers are warned ~7 days before each due date without an admin action.
    reminder_scheduler_enabled: bool = True
    reminder_scheduler_interval_hours: int = 12
    # Advance (lump-sum) prepayment charges: a flat bank fee plus a percentage
    # of the amount being prepaid.
    prepayment_flat_fee: float = 500.0
    prepayment_fee_percent: float = 1.0
    # Email alerts. When smtp_host is set, real emails are sent; otherwise the
    # message is stored + logged (still demonstrable, no credentials needed).
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_from: str = "no-reply@sajiloloan.example"
    # Two-factor login (email OTP) + payment webhook signing.
    otp_length: int = 6
    otp_expiry_minutes: int = 5
    otp_max_attempts: int = 5
    payment_webhook_secret: str = "change-me-payment-webhook-secret"
    # Payment rail: "khalti" (KPG-2 sandbox — the default; the customer pays on
    # Khalti's page and is redirected back, where the server verifies it and
    # shows/emails the receipt), "esewa" (ePay v2), "qr", "mock".
    payment_provider: str = "khalti"
    # Personal QR destination shown at checkout (the account that receives money).
    merchant_qr_name: str = "Sudin khanal"
    merchant_qr_phone: str = "9847697806"
    # Path/URL to the QR image. Drop your QR at frontend/public/esewa-qr.png, or
    # set NEXT_PUBLIC_MERCHANT_QR_URL / this to a full image URL.
    merchant_qr_url: str = "/esewa-qr.png"
    # Khalti sandbox secret key (from the Khalti dev portal). Pointed at the
    # sandbox base URL below, so no real money moves. Override via .env if needed.
    khalti_secret_key: str = "9804980dff2e409685a93a74ca199e47"
    # Sandbox default; live is https://khalti.com/api/v2
    khalti_base_url: str = "https://dev.khalti.com/api/v2"
    # eSewa ePay v2. Defaults are eSewa's public sandbox test merchant, so the
    # flow works out of the box; replace with your live merchant credentials.
    esewa_merchant_code: str = "EPAYTEST"
    esewa_secret_key: str = "8gBm/:&EnhH.1/q"
    esewa_form_url: str = "https://rc-epay.esewa.com.np/api/epay/main/v2/form"
    esewa_status_url: str = "https://rc.esewa.com.np/api/epay/transaction/status/"
    # Where the gateway redirects the customer back to (your frontend origin).
    payment_return_url_base: str = "http://localhost:3000"
    payment_website_url: str = "http://localhost:3000"
    # Core Banking Simulator (CBS): branch + currency used for account numbering.
    cbs_branch_code: str = "001"
    cbs_currency: str = "NPR"
    upload_dir: str = "uploads"
    max_upload_bytes: int = 10 * 1024 * 1024
    cors_allowed_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    auth_rate_limit_count: int = 10
    auth_rate_limit_window_seconds: int = 60
    expensive_rate_limit_count: int = 20
    expensive_rate_limit_window_seconds: int = 60
    # Late fee charged per overdue installment, as a percentage of the EMI.
    late_fee_percent: float = 5.0

    tesseract_cmd: str = ""
    # Tesseract OCR languages. "eng+nep" reads both English and Devanagari
    # (Nepali) so a citizenship name printed in देवनागरी can be extracted.
    # Requires the Nepali language pack (tesseract-ocr-nep / nep.traineddata);
    # if it is missing, OCR falls back to English automatically.
    ocr_languages: str = "eng+nep"

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
