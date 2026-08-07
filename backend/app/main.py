from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.cbs.routes import router as cbs_router
from app.config import get_settings
from app.database import close_database_connection
from app.routes.admin import router as admin_router
from app.routes.applications import router as applications_router
from app.routes.auth import router as auth_router
from app.routes.eligibility import eligibility_router, verification_router
from app.routes.emi import router as emi_router
from app.routes.flags import router as flags_router
from app.routes.health import router as health_router
from app.routes.kyc import router as kyc_router
from app.routes.loans import router as loans_router
from app.routes.payments import loans_payment_router, payments_router
from app.routes.notifications import router as notifications_router
from app.routes.ocr import router as ocr_router
from app.routes.officer import router as officer_router
from app.routes.rates import router as rates_router
from app.routes.risk import router as risk_router
from app.routes.settings import router as settings_router

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # Create indexes in production only; dev/test runs skip this so the test
    # suite never blocks on a real MongoDB connection.
    if settings.app_env.lower() == "production":
        try:
            from app.database import get_database
            from app.database.indexes import ensure_indexes

            await ensure_indexes(get_database())
        except Exception:  # noqa: BLE001 - startup must not fail on indexing
            pass

    # Automatic EMI reminder emails (~7 days before each due date). Skipped in
    # the test environment so the suite never spawns a background loop.
    reminder_task = None
    if settings.app_env.lower() != "test":
        try:
            from app.services.reminder_scheduler import start_reminder_scheduler

            reminder_task = start_reminder_scheduler()
        except Exception:  # noqa: BLE001 - startup must not fail on the scheduler
            reminder_task = None

    yield

    if reminder_task is not None:
        reminder_task.cancel()
    close_database_connection()


app = FastAPI(
    title=settings.app_name,
    description="Starter FastAPI app for the Sajilo Loan project.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.parsed_cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(health_router, tags=["health"])
app.include_router(auth_router)
app.include_router(applications_router)
app.include_router(notifications_router)
app.include_router(ocr_router)
app.include_router(risk_router)
app.include_router(emi_router)
app.include_router(settings_router)
app.include_router(rates_router)
app.include_router(eligibility_router)
app.include_router(verification_router)
app.include_router(loans_router)
app.include_router(kyc_router)
app.include_router(loans_payment_router)
app.include_router(payments_router)
app.include_router(flags_router)
app.include_router(officer_router)
app.include_router(admin_router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Sajilo Loan API starter"}
