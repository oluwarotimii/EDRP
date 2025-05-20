import random
import string
from typing import List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Path, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_, or_, desc

from app.database import get_db
from app.models.users import User, Role, USER_STATUS_PENDING, USER_STATUS_ACTIVE, USER_STATUS_REJECTED
from app.models.schools import School
from app.middleware.authentication import get_current_user
from app.services.auth import get_password_hash, verify_password
from app.schemas.onboarding import (
    SchoolRegistration,
    SchoolRegistrationResponse,
    JoinSchoolRequest,
    JoinSchoolResponse,
    UserApprovalAction,
    PendingUserResponse,
    RegenerateCodeResponse
)

router = APIRouter()

# Helper function to generate a random 5-digit join code
def generate_join_code():
    return ''.join(random.choices(string.digits, k=5))

# Helper function to set code expiration (3 days from now)
def generate_expiration_date():
    return datetime.utcnow() + timedelta(days=3)

@router.post("/schools", response_model=SchoolRegistrationResponse)
async def register_school(
    school_data: SchoolRegistration,
    db: AsyncSession = Depends(get_db)
):
    """
    Register a new school and create an admin user with a unique join code.
    """
    # Check if school name already exists
    result = await db.execute(select(School).where(School.name == school_data.school_name))
    if result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="School name already exists"
        )
    
    # Check if admin email already exists
    result = await db.execute(select(User).where(User.email == school_data.admin.email))
    if result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Generate a unique join code
    join_code = generate_join_code()
    while True:
        result = await db.execute(select(School).where(School.join_code == join_code))
        if not result.scalars().first():
            break
        join_code = generate_join_code()
    
    # Create expiration date (3 days from now)
    code_expires_at = generate_expiration_date()
    
    # Create the school
    abbreviation = ''.join([word[0].upper() for word in school_data.school_name.split()])
    
    # Check if abbreviation exists
    result = await db.execute(select(School).where(School.abbreviation == abbreviation))
    if result.scalars().first():
        # Add a random number to make it unique
        abbreviation += str(random.randint(1, 999))
    
    new_school = School(
        name=school_data.school_name,
        abbreviation=abbreviation,
        join_code=join_code,
        code_expires_at=code_expires_at
    )
    
    db.add(new_school)
    await db.commit()
    await db.refresh(new_school)
    
    # Find admin role or create if not exists
    result = await db.execute(select(Role).where(Role.name == "admin"))
    admin_role = result.scalars().first()
    
    if not admin_role:
        admin_role = Role(name="admin", description="School administrator")
        db.add(admin_role)
        await db.commit()
        await db.refresh(admin_role)
    
    # Create admin user
    hashed_password = get_password_hash(school_data.admin.password)
    
    admin_user = User(
        school_id=new_school.id,
        role_id=admin_role.id,
        full_name=school_data.admin.name,
        email=school_data.admin.email,
        hashed_password=hashed_password
    )
    
    db.add(admin_user)
    await db.commit()
    
    return SchoolRegistrationResponse(
        id=new_school.id,
        name=new_school.name,
        join_code=new_school.join_code,
        code_expires_at=new_school.code_expires_at
    )

@router.post("/join-school", response_model=JoinSchoolResponse)
async def join_school(
    join_data: JoinSchoolRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Allow teachers/staff to join a school using a join code.
    """
    # Check if join code exists and is valid
    result = await db.execute(
        select(School).where(
            and_(
                School.join_code == join_data.join_code,
                School.code_expires_at > datetime.utcnow()
            )
        )
    )
    school = result.scalars().first()
    
    if not school:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired join code"
        )
    
    # Check if email already exists
    result = await db.execute(select(User).where(User.email == join_data.email))
    if result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Find staff role or create if not exists
    result = await db.execute(select(Role).where(Role.name == "staff"))
    staff_role = result.scalars().first()
    
    if not staff_role:
        staff_role = Role(name="staff", description="School staff/teacher")
        db.add(staff_role)
        await db.commit()
        await db.refresh(staff_role)
    
    # Create user with pending status
    hashed_password = get_password_hash(join_data.password)
    
    new_user = User(
        school_id=school.id,
        role_id=staff_role.id,
        full_name=join_data.name,
        email=join_data.email,
        hashed_password=hashed_password,
        status=USER_STATUS_PENDING
    )
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    return JoinSchoolResponse(
        message="Registration successful, pending admin approval.",
        user_id=new_user.id
    )

@router.get("/users/pending", response_model=List[PendingUserResponse])
async def get_pending_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all pending users for the admin's school.
    """
    # Ensure user is an admin
    if current_user.role.name != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can view pending users"
        )
    
    # Get pending users from the admin's school
    result = await db.execute(
        select(User).where(
            and_(
                User.school_id == current_user.school_id,
                User.status == USER_STATUS_PENDING
            )
        ).order_by(User.created_at.desc())
    )
    
    pending_users = result.scalars().all()
    
    return pending_users

@router.put("/users/{user_id}/approve", response_model=PendingUserResponse)
async def approve_or_reject_user(
    user_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    action_data: UserApprovalAction = Body(...)
):
    """
    Approve or reject a pending user.
    """
    # Ensure user is an admin
    if current_user.role.name != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can approve users"
        )
    
    # Get the user to approve/reject
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Ensure user belongs to the admin's school
    if user.school_id != current_user.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only manage users from your school"
        )
    
    # Update user status based on action
    if action_data.action == "approve":
        user.status = USER_STATUS_ACTIVE
    else:  # reject
        user.status = USER_STATUS_REJECTED
    
    await db.commit()
    await db.refresh(user)
    
    return user

@router.post("/schools/{school_id}/regenerate-code", response_model=RegenerateCodeResponse)
async def regenerate_join_code(
    school_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Generate a new join code for a school.
    """
    # Ensure user is an admin
    if current_user.role.name != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can regenerate join codes"
        )
    
    # Ensure the school exists and admin belongs to that school
    result = await db.execute(select(School).where(School.id == school_id))
    school = result.scalars().first()
    
    if not school:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="School not found"
        )
    
    if school.id != current_user.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only regenerate codes for your school"
        )
    
    # Generate a new unique join code
    join_code = generate_join_code()
    while True:
        result = await db.execute(
            select(School).where(
                and_(
                    School.join_code == join_code,
                    School.id != school_id
                )
            )
        )
        if not result.scalars().first():
            break
        join_code = generate_join_code()
    
    # Update school with new join code and expiration date
    school.join_code = join_code
    school.code_expires_at = generate_expiration_date()
    
    await db.commit()
    await db.refresh(school)
    
    return RegenerateCodeResponse(
        join_code=school.join_code,
        code_expires_at=school.code_expires_at
    )