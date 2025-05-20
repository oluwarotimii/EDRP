from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import or_, and_

from app.database import get_db
from app.schemas.users import (
    UserCreate, UserUpdate, UserInDB, UserWithRole,
    RoleCreate, RoleUpdate, RoleInDB,
    PermissionCreate, PermissionInDB
)
from app.models.users import User, Role, Permission, RolePermission
from app.middleware.authentication import get_current_user, validate_admin_access
from app.services.auth import get_password_hash
from app.services.cloudinary import upload_image_to_cloudinary

router = APIRouter()

# Role endpoints
@router.post("/roles", response_model=RoleInDB, status_code=status.HTTP_201_CREATED)
async def create_role(
    role_data: RoleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new role (super_admin only).
    """
    # Only super_admin can create roles
    await validate_admin_access(current_user, db, super_admin_only=True)
    
    # Check if role with same name exists
    result = await db.execute(select(Role).where(Role.name == role_data.name))
    existing_role = result.scalars().first()
    if existing_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role with this name already exists"
        )
    
    # Create new role
    db_role = Role(**role_data.dict())
    db.add(db_role)
    await db.commit()
    await db.refresh(db_role)
    
    return db_role

@router.get("/roles", response_model=List[RoleInDB])
async def get_roles(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all roles.
    """
    # Admin users only
    await validate_admin_access(current_user, db)
    
    result = await db.execute(select(Role))
    roles = result.scalars().all()
    
    return roles

@router.get("/roles/{role_id}", response_model=RoleInDB)
async def get_role(
    role_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific role by ID.
    """
    # Admin users only
    await validate_admin_access(current_user, db)
    
    result = await db.execute(select(Role).where(Role.id == role_id))
    role = result.scalars().first()
    
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )
    
    return role

@router.put("/roles/{role_id}", response_model=RoleInDB)
async def update_role(
    role_data: RoleUpdate,
    role_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update a role (super_admin only).
    """
    # Only super_admin can update roles
    await validate_admin_access(current_user, db, super_admin_only=True)
    
    result = await db.execute(select(Role).where(Role.id == role_id))
    role = result.scalars().first()
    
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )
    
    # Update role attributes
    update_data = role_data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(role, key, value)
    
    await db.commit()
    await db.refresh(role)
    
    return role

# Permission endpoints
@router.post("/permissions", response_model=PermissionInDB, status_code=status.HTTP_201_CREATED)
async def create_permission(
    permission_data: PermissionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new permission (super_admin only).
    """
    # Only super_admin can create permissions
    await validate_admin_access(current_user, db, super_admin_only=True)
    
    # Check if permission with same name exists
    result = await db.execute(select(Permission).where(Permission.name == permission_data.name))
    existing_permission = result.scalars().first()
    if existing_permission:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Permission with this name already exists"
        )
    
    # Create new permission
    db_permission = Permission(**permission_data.dict())
    db.add(db_permission)
    await db.commit()
    await db.refresh(db_permission)
    
    return db_permission

@router.get("/permissions", response_model=List[PermissionInDB])
async def get_permissions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all permissions.
    """
    # Admin users only
    await validate_admin_access(current_user, db)
    
    result = await db.execute(select(Permission))
    permissions = result.scalars().all()
    
    return permissions

# Role-Permission endpoints
@router.post("/roles/{role_id}/permissions/{permission_id}", status_code=status.HTTP_200_OK)
async def assign_permission_to_role(
    role_id: int = Path(..., gt=0),
    permission_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Assign a permission to a role (super_admin only).
    """
    # Only super_admin can assign permissions
    await validate_admin_access(current_user, db, super_admin_only=True)
    
    # Check if role and permission exist
    role_result = await db.execute(select(Role).where(Role.id == role_id))
    role = role_result.scalars().first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )
    
    permission_result = await db.execute(select(Permission).where(Permission.id == permission_id))
    permission = permission_result.scalars().first()
    if not permission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Permission not found"
        )
    
    # Check if already assigned
    existing_result = await db.execute(
        select(RolePermission).where(
            and_(
                RolePermission.role_id == role_id,
                RolePermission.permission_id == permission_id
            )
        )
    )
    existing = existing_result.scalars().first()
    if existing:
        return {"detail": "Permission already assigned to role"}
    
    # Create new assignment
    db_role_permission = RolePermission(role_id=role_id, permission_id=permission_id)
    db.add(db_role_permission)
    await db.commit()
    
    return {"detail": "Permission assigned to role successfully"}

@router.delete("/roles/{role_id}/permissions/{permission_id}", status_code=status.HTTP_200_OK)
async def remove_permission_from_role(
    role_id: int = Path(..., gt=0),
    permission_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Remove a permission from a role (super_admin only).
    """
    # Only super_admin can remove permissions
    await validate_admin_access(current_user, db, super_admin_only=True)
    
    # Check if assignment exists
    existing_result = await db.execute(
        select(RolePermission).where(
            and_(
                RolePermission.role_id == role_id,
                RolePermission.permission_id == permission_id
            )
        )
    )
    existing = existing_result.scalars().first()
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Permission not assigned to role"
        )
    
    # Remove assignment
    await db.delete(existing)
    await db.commit()
    
    return {"detail": "Permission removed from role successfully"}

# User endpoints
@router.get("/users", response_model=List[UserWithRole])
async def get_users(
    school_id: Optional[int] = Query(None),
    role_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all users, with optional filtering by school, role, and search term.
    """
    # Build query
    query = select(User).join(Role)
    
    # Filter by school
    if school_id:
        # Check if user has access to this school
        if current_user.role.name != "super_admin" and current_user.school_id != school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view users from this school"
            )
        query = query.where(User.school_id == school_id)
    elif current_user.role.name != "super_admin":
        # Regular users can only see users from their own school
        query = query.where(User.school_id == current_user.school_id)
    
    # Filter by role
    if role_id:
        query = query.where(User.role_id == role_id)
    
    # Filter by search term
    if search:
        query = query.where(
            or_(
                User.full_name.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%")
            )
        )
    
    # Apply pagination
    query = query.offset(skip).limit(limit)
    
    # Execute query
    result = await db.execute(query)
    users = result.scalars().all()
    
    return users

@router.get("/users/{user_id}", response_model=UserWithRole)
async def get_user(
    user_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific user by ID.
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Check permissions: users can view their own profile or admins can view users from their school
    if user_id != current_user.id:
        if current_user.role.name != "super_admin" and (
            current_user.role.name not in ["admin_staff"] or 
            current_user.school_id != user.school_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view this user"
            )
    
    return user

@router.put("/users/{user_id}", response_model=UserInDB)
async def update_user(
    user_data: UserUpdate,
    user_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update a user.
    """
    # Get the user to update
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Check permissions: users can update their own profile or admins can update users from their school
    if user_id != current_user.id:
        if current_user.role.name != "super_admin" and (
            current_user.role.name not in ["admin_staff"] or 
            current_user.school_id != user.school_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update this user"
            )
    
    # Only admins can change roles
    if user_data.role_id is not None and current_user.role.name not in ["super_admin", "admin_staff"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to change user role"
        )
    
    # Update user attributes
    update_data = user_data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(user, key, value)
    
    await db.commit()
    await db.refresh(user)
    
    return user

@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a user (admin only).
    """
    # Only admins can delete users
    await validate_admin_access(current_user, db)
    
    # Get the user to delete
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Check permissions: admins can only delete users from their school
    if current_user.role.name != "super_admin" and current_user.school_id != user.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this user"
        )
    
    # Can't delete yourself
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )
    
    # Delete the user
    await db.delete(user)
    await db.commit()
    
    return None
