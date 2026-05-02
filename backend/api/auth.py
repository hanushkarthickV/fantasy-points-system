"""
Authentication routes — signup, login, token verification.

Uses JWT tokens with HS256.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta

import jwt
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from backend.db.base import get_db
from backend.db.models import User
from backend.logger import get_logger

logger = get_logger(__name__)
router_auth = APIRouter(prefix="/api/v2/auth")

JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 72


# ── Simple password hashing (bcrypt-like via hashlib for zero deps) ──────────
import hashlib
import secrets


def _hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    hashed = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
    return f"{salt}:{hashed}"


def _verify_password(password: str, stored: str) -> bool:
    if ":" not in stored:
        return False
    salt, hashed = stored.split(":", 1)
    return hashlib.sha256(f"{salt}{password}".encode()).hexdigest() == hashed


def _create_token(user_id: int, email: str) -> str:
    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_token(token: str) -> dict:
    """Decode and verify a JWT token. Raises HTTPException on failure."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")


# ── Request/Response models ──────────────────────────────────────────────────

class SignupRequest(BaseModel):
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    token: str
    email: str
    message: str


# ── Routes ────────────────────────────────────────────────────────────────────

@router_auth.post("/signup", response_model=AuthResponse)
async def signup(request: SignupRequest, db: Session = Depends(get_db)):
    """Register a new user."""
    existing = db.query(User).filter_by(email=request.email).first()
    if existing:
        raise HTTPException(409, "Email already registered")

    if len(request.password) < 6:
        raise HTTPException(422, "Password must be at least 6 characters")

    user = User(
        email=request.email,
        hashed_password=_hash_password(request.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = _create_token(user.id, user.email)
    logger.info("[AUTH] New user registered: %s", request.email)
    return AuthResponse(token=token, email=user.email, message="Account created successfully")


@router_auth.post("/login", response_model=AuthResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """Login with email and password."""
    user = db.query(User).filter_by(email=request.email).first()
    if not user or not user.hashed_password:
        raise HTTPException(401, "Invalid email or password")

    if not _verify_password(request.password, user.hashed_password):
        raise HTTPException(401, "Invalid email or password")

    token = _create_token(user.id, user.email)
    logger.info("[AUTH] User logged in: %s", request.email)
    return AuthResponse(token=token, email=user.email, message="Login successful")
