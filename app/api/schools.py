from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc, asc

from app.database import get_db
from app.schemas.schools import (
    SchoolCreate, SchoolUpdate, SchoolInDB,
    DepartmentCreate, DepartmentUpdate, DepartmentInDB,
    ClassCreate, ClassUpdate, ClassInDB,
    SubjectCreate, SubjectUpdate, SubjectInDB,
    AuthenticLocationCreate, AuthenticLocationUpdate, AuthenticLocationInDB
)
from app.models.schools import School, Department, Class, Subject, AuthenticLocation
from app.middleware.authentication import get_current_user, validate_admin_access, RoleChecker
from app.models.users import User

router = APIRouter()

# Role-based access control
allow_admin = RoleChecker(["super_admin", "admin_staff"])
allow_teachers = RoleChecker(["super_admin", "admin_staff", "class_teacher", "subject_teacher"])

# School endpoints
@router.post("/schools", response_model=SchoolInDB, status_code=status.HTTP_201_CREATED)
async def create_school(
    school_data: SchoolCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new school (super_admin only).
    """
    # Only super_admin can create schools
    await validate_admin_access(current_user, db, super_admin_only=True)
    
    # Check if school with same abbreviation exists
    result = await db.execute(select(School).where(School.abbreviation == school_data.abbreviation))
    existing_school = result.scalars().first()
    if existing_school:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="School with this abbreviation already exists"
        )
    
    # Create new school
    db_school = School(**school_data.dict())
    db.add(db_school)
    await db.commit()
    await db.refresh(db_school)
    
    return db_school

@router.get("/schools", response_model=List[SchoolInDB])
async def get_schools(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all schools (admin only).
    """
    await validate_admin_access(current_user, db)
    
    result = await db.execute(select(School).offset(skip).limit(limit))
    schools = result.scalars().all()
    
    return schools

@router.get("/schools/{school_id}", response_model=SchoolInDB)
async def get_school(
    school_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific school by ID.
    """
    # Regular users can only view their own school
    if current_user.role.name not in ["super_admin", "admin_staff"] and current_user.school_id != school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this school"
        )
    
    result = await db.execute(select(School).where(School.id == school_id))
    school = result.scalars().first()
    
    if not school:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="School not found"
        )
    
    return school

@router.put("/schools/{school_id}", response_model=SchoolInDB)
async def update_school(
    school_data: SchoolUpdate,
    school_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update a school (admin only).
    """
    await validate_admin_access(current_user, db)
    
    # Check if current user is from this school or super_admin
    if current_user.role.name != "super_admin" and current_user.school_id != school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this school"
        )
    
    result = await db.execute(select(School).where(School.id == school_id))
    school = result.scalars().first()
    
    if not school:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="School not found"
        )
    
    # Update school attributes
    update_data = school_data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(school, key, value)
    
    await db.commit()
    await db.refresh(school)
    
    return school

# Department endpoints
@router.post("/departments", response_model=DepartmentInDB, status_code=status.HTTP_201_CREATED)
async def create_department(
    department_data: DepartmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new department.
    """
    await validate_admin_access(current_user, db)
    
    # Validate school access
    if current_user.role.name != "super_admin" and current_user.school_id != department_data.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to create departments for this school"
        )
    
    # Create new department
    db_department = Department(**department_data.dict())
    db.add(db_department)
    await db.commit()
    await db.refresh(db_department)
    
    return db_department

@router.get("/departments", response_model=List[DepartmentInDB])
async def get_departments(
    school_id: Optional[int] = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all departments, optionally filtered by school_id.
    """
    query = select(Department)
    
    # Filter by school_id if provided, otherwise show only departments from user's school
    if school_id:
        # Check if user has access to the requested school
        if current_user.role.name != "super_admin" and current_user.school_id != school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view departments for this school"
            )
        query = query.where(Department.school_id == school_id)
    else:
        # Regular users can only see departments from their school
        if current_user.role.name != "super_admin":
            query = query.where(Department.school_id == current_user.school_id)
    
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    departments = result.scalars().all()
    
    return departments

@router.get("/departments/{department_id}", response_model=DepartmentInDB)
async def get_department(
    department_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific department by ID.
    """
    result = await db.execute(select(Department).where(Department.id == department_id))
    department = result.scalars().first()
    
    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found"
        )
    
    # Check if user has access to this department's school
    if current_user.role.name != "super_admin" and current_user.school_id != department.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this department"
        )
    
    return department

@router.put("/departments/{department_id}", response_model=DepartmentInDB)
async def update_department(
    department_data: DepartmentUpdate,
    department_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update a department (admin only).
    """
    await validate_admin_access(current_user, db)
    
    result = await db.execute(select(Department).where(Department.id == department_id))
    department = result.scalars().first()
    
    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found"
        )
    
    # Check if user has access to this department's school
    if current_user.role.name != "super_admin" and current_user.school_id != department.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this department"
        )
    
    # Update department attributes
    update_data = department_data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(department, key, value)
    
    await db.commit()
    await db.refresh(department)
    
    return department

# Class endpoints
@router.post("/classes", response_model=ClassInDB, status_code=status.HTTP_201_CREATED)
async def create_class(
    class_data: ClassCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new class.
    """
    await validate_admin_access(current_user, db)
    
    # Validate school access
    if current_user.role.name != "super_admin" and current_user.school_id != class_data.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to create classes for this school"
        )
    
    # Create new class
    db_class = Class(**class_data.dict())
    db.add(db_class)
    await db.commit()
    await db.refresh(db_class)
    
    return db_class

@router.get("/classes", response_model=List[ClassInDB])
async def get_classes(
    school_id: Optional[int] = Query(None),
    department_id: Optional[int] = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all classes, optionally filtered by school_id and/or department_id.
    """
    query = select(Class)
    
    # Apply filters
    if school_id:
        # Check if user has access to the requested school
        if current_user.role.name != "super_admin" and current_user.school_id != school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view classes for this school"
            )
        query = query.where(Class.school_id == school_id)
    else:
        # Regular users can only see classes from their school
        if current_user.role.name != "super_admin":
            query = query.where(Class.school_id == current_user.school_id)
    
    if department_id:
        query = query.where(Class.department_id == department_id)
    
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    classes = result.scalars().all()
    
    return classes

@router.get("/classes/{class_id}", response_model=ClassInDB)
async def get_class(
    class_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific class by ID.
    """
    result = await db.execute(select(Class).where(Class.id == class_id))
    class_ = result.scalars().first()
    
    if not class_:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Class not found"
        )
    
    # Check if user has access to this class's school
    if current_user.role.name != "super_admin" and current_user.school_id != class_.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this class"
        )
    
    return class_

@router.put("/classes/{class_id}", response_model=ClassInDB)
async def update_class(
    class_data: ClassUpdate,
    class_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update a class (admin only).
    """
    await validate_admin_access(current_user, db)
    
    result = await db.execute(select(Class).where(Class.id == class_id))
    class_ = result.scalars().first()
    
    if not class_:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Class not found"
        )
    
    # Check if user has access to this class's school
    if current_user.role.name != "super_admin" and current_user.school_id != class_.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this class"
        )
    
    # Update class attributes
    update_data = class_data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(class_, key, value)
    
    await db.commit()
    await db.refresh(class_)
    
    return class_

# Subject endpoints
@router.post("/subjects", response_model=SubjectInDB, status_code=status.HTTP_201_CREATED)
async def create_subject(
    subject_data: SubjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new subject.
    """
    await validate_admin_access(current_user, db)
    
    # Validate school access
    if current_user.role.name != "super_admin" and current_user.school_id != subject_data.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to create subjects for this school"
        )
    
    # Create new subject
    db_subject = Subject(**subject_data.dict())
    db.add(db_subject)
    await db.commit()
    await db.refresh(db_subject)
    
    return db_subject

@router.get("/subjects", response_model=List[SubjectInDB])
async def get_subjects(
    school_id: Optional[int] = Query(None),
    department_id: Optional[int] = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all subjects, optionally filtered by school_id and/or department_id.
    """
    query = select(Subject)
    
    # Apply filters
    if school_id:
        # Check if user has access to the requested school
        if current_user.role.name != "super_admin" and current_user.school_id != school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view subjects for this school"
            )
        query = query.where(Subject.school_id == school_id)
    else:
        # Regular users can only see subjects from their school
        if current_user.role.name != "super_admin":
            query = query.where(Subject.school_id == current_user.school_id)
    
    if department_id:
        query = query.where(Subject.department_id == department_id)
    
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    subjects = result.scalars().all()
    
    return subjects

@router.get("/subjects/{subject_id}", response_model=SubjectInDB)
async def get_subject(
    subject_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific subject by ID.
    """
    result = await db.execute(select(Subject).where(Subject.id == subject_id))
    subject = result.scalars().first()
    
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subject not found"
        )
    
    # Check if user has access to this subject's school
    if current_user.role.name != "super_admin" and current_user.school_id != subject.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this subject"
        )
    
    return subject

@router.put("/subjects/{subject_id}", response_model=SubjectInDB)
async def update_subject(
    subject_data: SubjectUpdate,
    subject_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update a subject (admin only).
    """
    await validate_admin_access(current_user, db)
    
    result = await db.execute(select(Subject).where(Subject.id == subject_id))
    subject = result.scalars().first()
    
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subject not found"
        )
    
    # Check if user has access to this subject's school
    if current_user.role.name != "super_admin" and current_user.school_id != subject.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this subject"
        )
    
    # Update subject attributes
    update_data = subject_data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(subject, key, value)
    
    await db.commit()
    await db.refresh(subject)
    
    return subject

# Authentic Location endpoints
@router.post("/authentic-locations", response_model=AuthenticLocationInDB, status_code=status.HTTP_201_CREATED)
async def create_authentic_location(
    location_data: AuthenticLocationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new authentic location for GPS verification.
    """
    await validate_admin_access(current_user, db)
    
    # Validate school access
    if current_user.role.name != "super_admin" and current_user.school_id != location_data.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to create locations for this school"
        )
    
    # Create new location
    db_location = AuthenticLocation(**location_data.dict())
    db.add(db_location)
    await db.commit()
    await db.refresh(db_location)
    
    return db_location

@router.get("/authentic-locations", response_model=List[AuthenticLocationInDB])
async def get_authentic_locations(
    school_id: Optional[int] = Query(None),
    active_only: bool = Query(True),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all authentic locations, optionally filtered by school_id and active status.
    """
    query = select(AuthenticLocation)
    
    # Apply filters
    if school_id:
        # Check if user has access to the requested school
        if current_user.role.name != "super_admin" and current_user.school_id != school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view locations for this school"
            )
        query = query.where(AuthenticLocation.school_id == school_id)
    else:
        # Regular users can only see locations from their school
        if current_user.role.name != "super_admin":
            query = query.where(AuthenticLocation.school_id == current_user.school_id)
    
    if active_only:
        query = query.where(AuthenticLocation.active == True)
    
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    locations = result.scalars().all()
    
    return locations

@router.get("/authentic-locations/{location_id}", response_model=AuthenticLocationInDB)
async def get_authentic_location(
    location_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific authentic location by ID.
    """
    result = await db.execute(select(AuthenticLocation).where(AuthenticLocation.id == location_id))
    location = result.scalars().first()
    
    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Authentic location not found"
        )
    
    # Check if user has access to this location's school
    if current_user.role.name != "super_admin" and current_user.school_id != location.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this location"
        )
    
    return location

@router.put("/authentic-locations/{location_id}", response_model=AuthenticLocationInDB)
async def update_authentic_location(
    location_data: AuthenticLocationUpdate,
    location_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update an authentic location (admin only).
    """
    await validate_admin_access(current_user, db)
    
    result = await db.execute(select(AuthenticLocation).where(AuthenticLocation.id == location_id))
    location = result.scalars().first()
    
    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Authentic location not found"
        )
    
    # Check if user has access to this location's school
    if current_user.role.name != "super_admin" and current_user.school_id != location.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this location"
        )
    
    # Update location attributes
    update_data = location_data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(location, key, value)
    
    await db.commit()
    await db.refresh(location)
    
    return location
