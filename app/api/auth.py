from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, Body, Request
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import or_

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.database import get_db
from app.schemas.users import UserCreate, UserInDB, Token, TokenData, LoginRequest, PasswordChange
from app.models.users import User, Role
from app.config import settings
from app.services.auth import create_access_token, authenticate_user, get_password_hash
from app.middleware.authentication import get_current_user

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

@router.post("/auth/register", response_model=UserInDB, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Register a new user.
    """
    # Check if email already exists
    result = await db.execute(select(User).where(User.email == user_data.email))
    existing_user = result.scalars().first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Check if role exists
    result = await db.execute(select(Role).where(Role.id == user_data.role_id))
    role = result.scalars().first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role does not exist"
        )
    
    # Create new user
    hashed_password = get_password_hash(user_data.password)
    db_user = User(
        school_id=user_data.school_id,
        role_id=user_data.role_id,
        full_name=user_data.full_name,
        email=user_data.email,
        phone=user_data.phone,
        profile_photo_url=user_data.profile_photo_url,
        hashed_password=hashed_password
    )
    
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    
    return db_user

@router.post("/auth/login", response_model=Token)
async def login_for_access_token(
    form_data: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Authenticate a user and return an access token.
    """
    user = await authenticate_user(form_data.email, form_data.password, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Get role name
    result = await db.execute(select(Role).where(Role.id == user.role_id))
    role = result.scalars().first()
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id), "role": role.name, "school_id": user.school_id},
        expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user.id,
        "role": role.name
    }

@router.post("/auth/change-password", status_code=status.HTTP_200_OK)
async def change_password(
    password_data: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Change user password.
    """
    # Verify old password
    if not pwd_context.verify(password_data.old_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect password"
        )
    
    # Update password
    hashed_password = get_password_hash(password_data.new_password)
    current_user.hashed_password = hashed_password
    
    db.add(current_user)
    await db.commit()
    
    return {"detail": "Password updated successfully"}

@router.get("/auth/me", response_model=UserInDB)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """
    Get information about the currently authenticated user.
    """
    return current_user
