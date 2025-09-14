import os
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .logging_config import configure_logging
from .database import get_db, init_db, Account
from .app.runtime.gpu_guard import initialize_gpu_guard
from .routers import videos, health
from .schemas.responses import UserRegistration, UserResponse

configure_logging()

init_db()
initialize_gpu_guard()

app = FastAPI(title="SafeLens API", version="1.0.0")


# Optional CORS (disabled by default). Enable with CORS_ENABLED=true
def _parse_list_env(name: str, default: str = ""):
    value = os.getenv(name, default)
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


CORS_ENABLED = os.getenv("CORS_ENABLED", "false").strip().lower() in {
    "1",
    "true",
    "yes",
}
if CORS_ENABLED:
    allow_origins = _parse_list_env(
        "CORS_ALLOW_ORIGINS", os.getenv("FRONTEND_ORIGINS", "")
    )
    if not allow_origins:
        allow_origins = ["*"]
    allow_credentials = os.getenv("CORS_ALLOW_CREDENTIALS", "true").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    allow_methods = _parse_list_env("CORS_ALLOW_METHODS", "*") or ["*"]
    allow_headers = _parse_list_env("CORS_ALLOW_HEADERS", "*") or ["*"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=allow_credentials,
        allow_methods=allow_methods,
        allow_headers=allow_headers,
    )

app.include_router(videos.router, prefix="/api")
app.include_router(health.router)


@app.post("/api/auth/register", response_model=UserResponse)
async def register_user(
    user_data: UserRegistration,
    db: Session = Depends(get_db),
):
    """Register a new user account from Auth.js session data"""
    import logging

    logger = logging.getLogger(__name__)

    try:
        logger.info(
            f"Registration request - CUID: {user_data.id}, UUID: {user_data.session_uuid}, Email: {user_data.email}"
        )

        existing_user = db.query(Account).filter(Account.id == user_data.id).first()
        if existing_user:
            if existing_user.session_uuid != user_data.session_uuid:
                existing_user.session_uuid = user_data.session_uuid
                db.commit()
                logger.info(
                    f"Updated session UUID for existing user: {user_data.email}"
                )

            return UserResponse(
                id=existing_user.id,
                name=existing_user.name,
                email=existing_user.email,
                image=existing_user.image,
                created_at=existing_user.created_at,
            )

        existing_email = (
            db.query(Account).filter(Account.email == user_data.email).first()
        )
        if existing_email:
            raise HTTPException(
                status_code=409,
                detail="Email address is already registered with a different account",
            )

        new_account = Account(
            id=user_data.id,
            session_uuid=user_data.session_uuid,
            name=user_data.name,
            email=user_data.email,
            image=user_data.image,
        )

        db.add(new_account)
        db.commit()
        db.refresh(new_account)

        logger.info(f"Successfully registered new user: {user_data.email}")

        return UserResponse(
            id=new_account.id,
            name=new_account.name,
            email=new_account.email,
            image=new_account.image,
            created_at=new_account.created_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error registering user {user_data.email}: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to register user account")
