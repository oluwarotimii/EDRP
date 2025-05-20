from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path, File, UploadFile, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import or_, and_, func, desc, asc

from app.database import get_db
from app.schemas.users import UserCreate, UserUpdate, UserWithRole, TeacherSubjectClassCreate, TeacherSubjectClassInDB
from app.models.users import User, Role, TeacherSubjectClass
from app.models.schools import School, Class, Department, Subject
from app.middleware.authentication import get_current_user, validate_admin_access, RoleChecker
from app.services.auth import get_password_hash
from app.services.cloudinary import upload_image_to_cloudinary

router = APIRouter()

# Role-based access control
allow_teacher_management = RoleChecker(["super_admin", "admin_staff"])

# Teacher endpoints
@router.post("/teachers", status_code=status.HTTP_201_CREATED, response_model=UserWithRole)
async def create_teacher(
    school_id: int = Form(...),
    full_name: str = Form(...),
    email: str = Form(...),
    phone: Optional[str] = Form(None),
    department_id: Optional[int] = Form(None),
    password: str = Form(...),
    profile_photo: Optional[UploadFile] = File(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new teacher account.
    """
    # Check if user has permission to create teachers
    await validate_admin_access(current_user, db)
    
    # Validate school access
    if current_user.role.name != "super_admin" and current_user.school_id != school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to create teachers for this school"
        )
    
    # Validate that the school exists
    school_result = await db.execute(select(School).where(School.id == school_id))
    school = school_result.scalars().first()
    if not school:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="School not found"
        )
    
    # Check if email is already in use
    email_result = await db.execute(select(User).where(User.email == email))
    existing_user = email_result.scalars().first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already in use"
        )
    
    # Upload profile photo to Cloudinary if provided
    profile_photo_url = None
    if profile_photo:
        try:
            profile_photo_url = await upload_image_to_cloudinary(profile_photo)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error uploading image: {str(e)}"
            )
    
    # Get the teacher role
    role_result = await db.execute(select(Role).where(Role.name.in_(["class_teacher", "subject_teacher"])))
    teacher_roles = role_result.scalars().all()
    if not teacher_roles:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Teacher roles not found"
        )
    
    # Use class_teacher role by default
    teacher_role = next((r for r in teacher_roles if r.name == "class_teacher"), teacher_roles[0])
    
    # Create user record
    hashed_password = get_password_hash(password)
    user = User(
        school_id=school_id,
        role_id=teacher_role.id,
        full_name=full_name,
        email=email,
        phone=phone,
        profile_photo_url=profile_photo_url,
        hashed_password=hashed_password
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    # Refresh user to include role information
    await db.refresh(user)
    
    return user

@router.get("/teachers", response_model=List[UserWithRole])
async def get_teachers(
    school_id: Optional[int] = Query(None),
    department_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all teachers, with optional filtering.
    """
    # Get teacher role IDs
    role_result = await db.execute(select(Role).where(Role.name.in_(["class_teacher", "subject_teacher"])))
    teacher_roles = role_result.scalars().all()
    teacher_role_ids = [role.id for role in teacher_roles]
    
    if not teacher_role_ids:
        return []
    
    # Basic query
    query = select(User).where(User.role_id.in_(teacher_role_ids))
    
    # Apply filters
    if school_id:
        # Check if user has access to the requested school
        if current_user.role.name != "super_admin" and current_user.school_id != school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view teachers for this school"
            )
        query = query.where(User.school_id == school_id)
    else:
        # Regular users can only see teachers from their school
        if current_user.role.name != "super_admin":
            query = query.where(User.school_id == current_user.school_id)
    
    if department_id:
        # Filtering by department requires joining with TeacherSubjectClass and Subject
        # This is a simplification - in reality you might want to join with department directly
        query = query.join(
            TeacherSubjectClass, 
            User.id == TeacherSubjectClass.teacher_user_id
        ).join(
            Subject, 
            TeacherSubjectClass.subject_id == Subject.id
        ).where(
            Subject.department_id == department_id
        ).distinct()
    
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
    teachers = result.scalars().all()
    
    return teachers

@router.get("/teachers/{teacher_id}", response_model=UserWithRole)
async def get_teacher(
    teacher_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific teacher by ID.
    """
    # Get teacher roles
    role_result = await db.execute(select(Role).where(Role.name.in_(["class_teacher", "subject_teacher"])))
    teacher_roles = role_result.scalars().all()
    teacher_role_ids = [role.id for role in teacher_roles]
    
    if not teacher_role_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Teacher roles not defined in the system"
        )
    
    # Get the teacher
    result = await db.execute(
        select(User).where(and_(User.id == teacher_id, User.role_id.in_(teacher_role_ids)))
    )
    teacher = result.scalars().first()
    
    if not teacher:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Teacher not found"
        )
    
    # Check if user has access to this teacher's school
    if current_user.role.name != "super_admin" and current_user.school_id != teacher.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view teachers from another school"
        )
    
    return teacher

@router.post("/teachers/assign", response_model=TeacherSubjectClassInDB)
async def assign_teacher_to_subject_class(
    assignment: TeacherSubjectClassCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Assign a teacher to teach a subject in a class.
    """
    # Check if user has permission
    await validate_admin_access(current_user, db)
    
    # Validate teacher exists and is actually a teacher
    teacher_result = await db.execute(
        select(User).join(Role).where(
            and_(
                User.id == assignment.teacher_user_id,
                Role.name.in_(["class_teacher", "subject_teacher"])
            )
        )
    )
    teacher = teacher_result.scalars().first()
    if not teacher:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Teacher not found or user is not a teacher"
        )
    
    # Validate subject exists
    subject_result = await db.execute(select(Subject).where(Subject.id == assignment.subject_id))
    subject = subject_result.scalars().first()
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subject not found"
        )
    
    # Validate class exists
    class_result = await db.execute(select(Class).where(Class.id == assignment.class_id))
    class_ = class_result.scalars().first()
    if not class_:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Class not found"
        )
    
    # Check if user has access to teacher's school
    if current_user.role.name != "super_admin" and current_user.school_id != teacher.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to assign teachers from another school"
        )
    
    # Check if subject and class are from the same school as the teacher
    if subject.school_id != teacher.school_id or class_.school_id != teacher.school_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Teacher, subject, and class must be from the same school"
        )
    
    # Check if assignment already exists
    existing_result = await db.execute(
        select(TeacherSubjectClass).where(
            and_(
                TeacherSubjectClass.teacher_user_id == assignment.teacher_user_id,
                TeacherSubjectClass.subject_id == assignment.subject_id,
                TeacherSubjectClass.class_id == assignment.class_id
            )
        )
    )
    existing = existing_result.scalars().first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This teacher is already assigned to teach this subject in this class"
        )
    
    # Create the assignment
    db_assignment = TeacherSubjectClass(**assignment.dict())
    db.add(db_assignment)
    await db.commit()
    
    return db_assignment

@router.delete("/teachers/assignments/{teacher_id}/{subject_id}/{class_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_teacher_assignment(
    teacher_id: int,
    subject_id: int,
    class_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Remove a teacher's assignment to teach a subject in a class.
    """
    # Check if user has permission
    await validate_admin_access(current_user, db)
    
    # Find the assignment
    result = await db.execute(
        select(TeacherSubjectClass).where(
            and_(
                TeacherSubjectClass.teacher_user_id == teacher_id,
                TeacherSubjectClass.subject_id == subject_id,
                TeacherSubjectClass.class_id == class_id
            )
        )
    )
    assignment = result.scalars().first()
    
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assignment not found"
        )
    
    # Verify access permission - get teacher to check school_id
    teacher_result = await db.execute(select(User).where(User.id == teacher_id))
    teacher = teacher_result.scalars().first()
    
    if current_user.role.name != "super_admin" and current_user.school_id != teacher.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to manage assignments for teachers from another school"
        )
    
    # Remove the assignment
    await db.delete(assignment)
    await db.commit()
    
    return None

@router.get("/teachers/{teacher_id}/assignments", response_model=List[dict])
async def get_teacher_assignments(
    teacher_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all subject-class assignments for a teacher.
    """
    # Verify the teacher exists
    teacher_result = await db.execute(
        select(User).join(Role).where(
            and_(
                User.id == teacher_id,
                Role.name.in_(["class_teacher", "subject_teacher"])
            )
        )
    )
    teacher = teacher_result.scalars().first()
    
    if not teacher:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Teacher not found or user is not a teacher"
        )
    
    # Check if user has access to teacher's school
    if current_user.role.name != "super_admin" and current_user.school_id != teacher.school_id:
        if current_user.id != teacher_id:  # Teachers can view their own assignments
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view assignments for teachers from another school"
            )
    
    # Get assignments with subject and class names
    assignments_result = await db.execute(
        select(
            TeacherSubjectClass,
            Subject.name.label("subject_name"),
            Class.name.label("class_name")
        ).join(
            Subject,
            TeacherSubjectClass.subject_id == Subject.id
        ).join(
            Class,
            TeacherSubjectClass.class_id == Class.id
        ).where(
            TeacherSubjectClass.teacher_user_id == teacher_id
        )
    )
    
    assignments = []
    for row in assignments_result:
        assignment = row[0]
        subject_name = row[1]
        class_name = row[2]
        
        assignments.append({
            "teacher_user_id": assignment.teacher_user_id,
            "subject_id": assignment.subject_id,
            "subject_name": subject_name,
            "class_id": assignment.class_id,
            "class_name": class_name
        })
    
    return assignments
