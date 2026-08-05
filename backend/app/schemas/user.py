from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

COMMON_PASSWORDS = {
    "password",
    "password123",
    "12345678",
    "123456789",
    "qwerty123",
    "admin1234",
}


class UserRole(StrEnum):
    CUSTOMER = "customer"
    OFFICER = "officer"
    ADMIN = "admin"


class UserRegisterRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    phone: str = Field(..., min_length=7, max_length=20)
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("full_name", "phone")
    @classmethod
    def strip_and_require_value(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Value cannot be empty")
        return value

    @field_validator("email")
    @classmethod
    def require_gmail(cls, value: EmailStr) -> EmailStr:
        # Registration is restricted to Gmail addresses; the account is then
        # activated only after the emailed OTP is verified.
        if not str(value).lower().strip().endswith("@gmail.com"):
            raise ValueError("Registration requires a valid @gmail.com email address.")
        return value

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        allowed = set("0123456789+-() ")
        if any(character not in allowed for character in value):
            raise ValueError("Phone can contain only digits, spaces, +, -, (, and )")
        return value

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        if value.lower() in COMMON_PASSWORDS:
            raise ValueError("Password is too common")
        if not any(character.islower() for character in value):
            raise ValueError("Password must include a lowercase letter")
        if not any(character.isupper() for character in value):
            raise ValueError("Password must include an uppercase letter")
        if not any(character.isdigit() for character in value):
            raise ValueError("Password must include a number")
        if not any(not character.isalnum() for character in value):
            raise ValueError("Password must include a symbol")
        return value


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)


class UserResponse(BaseModel):
    id: str
    full_name: str
    email: EmailStr
    phone: str
    role: UserRole
    is_blacklisted: bool = False
    mfa_enabled: bool = False
    email_verified: bool = True
    kyc_status: str = "not_started"
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class LoginResponse(BaseModel):
    """A token, an MFA challenge, or an email-verification challenge (OTP emailed)."""

    mfa_required: bool = False
    verification_required: bool = False
    access_token: str | None = None
    token_type: str | None = None
    user: UserResponse | None = None
    email: str | None = None


class RegisterResponse(BaseModel):
    """Registration always requires email verification before activation."""

    verification_required: bool = True
    email: str


class VerifyOtpRequest(BaseModel):
    email: EmailStr
    otp: str = Field(..., min_length=4, max_length=10)


class MfaStatusResponse(BaseModel):
    mfa_enabled: bool
