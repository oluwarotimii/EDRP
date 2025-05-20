from datetime import datetime, timedelta
from typing import Optional, List, Callable, Union

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.config import settings
from app.database import get_db
from app.models.users import User, Role, Permission, RolePermission

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

async def get_current_user(
    token: str = Depends(oauth2_scheme), 
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Get the current authenticated user from the provided JWT token.
    
    Args:
        token: The JWT token
        db: Database session
        
    Returns:
        The authenticated user
        
    Raises:
        HTTPException: If token is invalid or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Decode the JWT token
        payload = jwt.decode(
            token, 
            settings.SECRET_KEY, 
            algorithms=[settings.ALGORITHM]
        )
        
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        
        # Check token expiration
        token_exp = payload.get("exp")
        if token_exp is None:
            raise credentials_exception
        
        if datetime.fromtimestamp(token_exp) < datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
    except JWTError:
        raise credentials_exception
    
    # Get the user from database
    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalars().first()
    
    if user is None:
        raise credentials_exception
    
    return user

async def validate_admin_access(user: User, db: AsyncSession, super_admin_only: bool = False) -> None:
    """
    Validate that a user has admin access.
    
    Args:
        user: The user to check
        db: Database session
        super_admin_only: Whether to only allow super_admin role
        
    Raises:
        HTTPException: If user doesn't have required role
    """
    # Get the user's role
    result = await db.execute(select(Role).where(Role.id == user.role_id))
    role = result.scalars().first()
    
    if not role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User role not found"
        )
    
    if super_admin_only and role.name != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This action requires super admin privileges"
        )
    
    if not super_admin_only and role.name not in ["super_admin", "admin_staff"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This action requires admin privileges"
        )

class RoleChecker:
    """
    Dependency for checking if a user has the required role(s).
    """
    def __init__(self, allowed_roles: List[str]):
        self.allowed_roles = allowed_roles
    
    async def __call__(self, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> bool:
        result = await db.execute(select(Role).where(Role.id == user.role_id))
        role = result.scalars().first()
        
        if not role:
            return False
        
        if role.name in self.allowed_roles:
            return True
        
        return False
    
    async def check_permission(self, user: User, db: AsyncSession) -> bool:
        """
        Check if a user has any of the allowed roles.
        
        Args:
            user: The user to check
            db: Database session
            
        Returns:
            True if the user has one of the allowed roles, False otherwise
        """
        return await self(user, db)

# Middleware to extract authentication info from request
async def auth_middleware(request: Request, call_next):
    """
    Middleware to extract authentication info from request and attach it to request state.
    """
    response = await call_next(request)
    return response
