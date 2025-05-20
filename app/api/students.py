from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path, File, UploadFile, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import or_, and_, func

from app.database import get_db
from app.schemas.users import UserCreate, StudentCreate, StudentUpdate, StudentInDB, StudentWithUser, ParentStudentCreate
from app.models.users import User, Student, ParentStudent, Role
from app.models.schools import School, Class, Department
from app.models.academics import AcademicSession
from app.middleware.authentication import get_current_user, validate_admin_access, RoleChecker
from app.services.auth import get_password_hash
from app.services.cloudinary import upload_image_to_cloudinary

router = APIRouter()

# Role-based access control
allow_student_management = RoleChecker(["super_admin", "admin_staff"])

# Helper function to generate admission number
async def generate_admission_number(school_abbreviation, db: AsyncSession):
    """Generate a unique admission number based on school abbreviation and year."""
    from datetime import datetime
    
    year = datetime.now().year
    
    # Get the last admission number for this school and year
    query = select(func.count(Student.id)).join(School).where(
        and_(
            School.abbreviation == school_abbreviation,
            Student.admission_number.like(f"{school_abbreviation}/{year}/%")
        )
    )
    result = await db.execute(query)
    count = result.scalar() or 0
    
    # Generate the new number
    next_number = count + 1
    admission_number = f"{school_abbreviation}/{year}/{next_number:04d}"
    
    return admission_number

# Student endpoints
@router.post("/students", response_model=StudentWithUser, status_code=status.HTTP_201_CREATED)
async def create_student(
    school_id: int = Form(...),
    full_name: str = Form(...),
    email: str = Form(...),
    date_of_birth: str = Form(...),
    gender: Optional[str] = Form(None),
    class_id: Optional[int] = Form(None),
    department_id: Optional[int] = Form(None),
    session_id: Optional[int] = Form(None),
    phone: Optional[str] = Form(None),
    photo: Optional[UploadFile] = File(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new student with user account.
    """
    # Check if user has permission to create students
    await validate_admin_access(current_user, db)
    
    # Validate school access
    if current_user.role.name != "super_admin" and current_user.school_id != school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to create students for this school"
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
    
    # Upload photo to Cloudinary if provided
    photo_url = None
    if photo:
        try:
            photo_url = await upload_image_to_cloudinary(photo)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error uploading image: {str(e)}"
            )
    
    # Get the student role
    role_result = await db.execute(select(Role).where(Role.name == "student"))
    student_role = role_result.scalars().first()
    if not student_role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student role not found"
        )
    
    # Generate a temporary password (first 3 letters of name + last 4 of email + birth year)
    from datetime import datetime
    birth_year = datetime.strptime(date_of_birth, "%Y-%m-%d").year
    temp_password = f"{full_name[:3].lower()}{email[-4:].lower()}{birth_year}"
    
    # Create user record
    hashed_password = get_password_hash(temp_password)
    user = User(
        school_id=school_id,
        role_id=student_role.id,
        full_name=full_name,
        email=email,
        phone=phone,
        profile_photo_url=photo_url,
        hashed_password=hashed_password
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    # Generate admission number
    admission_number = await generate_admission_number(school.abbreviation, db)
    
    # Create student record
    student = Student(
        user_id=user.id,
        school_id=school_id,
        admission_number=admission_number,
        date_of_birth=datetime.strptime(date_of_birth, "%Y-%m-%d"),
        gender=gender,
        class_id=class_id,
        department_id=department_id,
        session_id=session_id,
        photo_url=photo_url
    )
    db.add(student)
    await db.commit()
    await db.refresh(student)
    
    # Refresh user to include role information
    await db.refresh(user)
    
    return {**student.__dict__, "user": user}

@router.get("/students", response_model=List[StudentWithUser])
async def get_students(
    school_id: Optional[int] = Query(None),
    class_id: Optional[int] = Query(None),
    department_id: Optional[int] = Query(None),
    session_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all students, with optional filtering.
    """
    # Basic query
    query = select(Student).join(User)
    
    # Apply filters
    if school_id:
        # Check if user has access to the requested school
        if current_user.role.name != "super_admin" and current_user.school_id != school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view students for this school"
            )
        query = query.where(Student.school_id == school_id)
    else:
        # Regular users can only see students from their school
        if current_user.role.name != "super_admin":
            query = query.where(Student.school_id == current_user.school_id)
    
    if class_id:
        query = query.where(Student.class_id == class_id)
    
    if department_id:
        query = query.where(Student.department_id == department_id)
    
    if session_id:
        query = query.where(Student.session_id == session_id)
    
    if search:
        query = query.where(
            or_(
                User.full_name.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%"),
                Student.admission_number.ilike(f"%{search}%")
            )
        )
    
    # Apply pagination
    query = query.offset(skip).limit(limit)
    
    # Execute query
    result = await db.execute(query)
    students = result.scalars().all()
    
    # Load user for each student
    student_user_list = []
    for student in students:
        user_result = await db.execute(select(User).where(User.id == student.user_id))
        user = user_result.scalars().first()
        student_user_list.append({**student.__dict__, "user": user})
    
    return student_user_list

@router.get("/students/{student_id}", response_model=StudentWithUser)
async def get_student(
    student_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific student by ID.
    """
    result = await db.execute(select(Student).where(Student.id == student_id))
    student = result.scalars().first()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found"
        )
    
    # Check if user has access to this student's school
    if current_user.role.name != "super_admin" and current_user.school_id != student.school_id:
        # Check if the current user is a parent of this student
        if current_user.role.name == "parent":
            parent_result = await db.execute(
                select(ParentStudent).where(
                    and_(
                        ParentStudent.parent_user_id == current_user.id,
                        ParentStudent.student_id == student_id
                    )
                )
            )
            parent_link = parent_result.scalars().first()
            if not parent_link:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to view this student"
                )
        else:
            # For teachers and other staff
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view students from another school"
            )
    
    # Get user data
    user_result = await db.execute(select(User).where(User.id == student.user_id))
    user = user_result.scalars().first()
    
    return {**student.__dict__, "user": user}

@router.put("/students/{student_id}", response_model=StudentWithUser)
async def update_student(
    student_data: StudentUpdate,
    student_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update a student.
    """
    # Check if student exists
    result = await db.execute(select(Student).where(Student.id == student_id))
    student = result.scalars().first()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found"
        )
    
    # Check if user has permission to update this student
    if current_user.role.name != "super_admin" and current_user.school_id != student.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this student"
        )
    
    if current_user.role.name not in ["super_admin", "admin_staff"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can update student records"
        )
    
    # Update student attributes
    update_data = student_data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(student, key, value)
    
    await db.commit()
    await db.refresh(student)
    
    # Get updated user data
    user_result = await db.execute(select(User).where(User.id == student.user_id))
    user = user_result.scalars().first()
    
    return {**student.__dict__, "user": user}

@router.post("/students/{student_id}/parents/{parent_user_id}", status_code=status.HTTP_201_CREATED)
async def link_parent_to_student(
    student_id: int = Path(..., gt=0),
    parent_user_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Link a parent to a student.
    """
    # Check if user has permission to manage student-parent relationships
    await validate_admin_access(current_user, db)
    
    # Check if student exists
    student_result = await db.execute(select(Student).where(Student.id == student_id))
    student = student_result.scalars().first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found"
        )
    
    # Check if user has access to this student's school
    if current_user.role.name != "super_admin" and current_user.school_id != student.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to manage students from another school"
        )
    
    # Check if parent exists and has the parent role
    parent_result = await db.execute(
        select(User).join(Role).where(
            and_(
                User.id == parent_user_id,
                Role.name == "parent"
            )
        )
    )
    parent = parent_result.scalars().first()
    if not parent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Parent not found or user is not a parent"
        )
    
    # Check if parent and student are from the same school
    if parent.school_id != student.school_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Parent and student must be from the same school"
        )
    
    # Check if link already exists
    existing_result = await db.execute(
        select(ParentStudent).where(
            and_(
                ParentStudent.parent_user_id == parent_user_id,
                ParentStudent.student_id == student_id
            )
        )
    )
    existing = existing_result.scalars().first()
    if existing:
        return {"detail": "Parent already linked to this student"}
    
    # Create the link
    parent_student = ParentStudent(
        parent_user_id=parent_user_id,
        student_id=student_id
    )
    db.add(parent_student)
    await db.commit()
    
    return {"detail": "Parent linked to student successfully"}

@router.delete("/students/{student_id}/parents/{parent_user_id}", status_code=status.HTTP_200_OK)
async def unlink_parent_from_student(
    student_id: int = Path(..., gt=0),
    parent_user_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Remove link between a parent and a student.
    """
    # Check if user has permission to manage student-parent relationships
    await validate_admin_access(current_user, db)
    
    # Check if student exists
    student_result = await db.execute(select(Student).where(Student.id == student_id))
    student = student_result.scalars().first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found"
        )
    
    # Check if user has access to this student's school
    if current_user.role.name != "super_admin" and current_user.school_id != student.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to manage students from another school"
        )
    
    # Check if link exists
    link_result = await db.execute(
        select(ParentStudent).where(
            and_(
                ParentStudent.parent_user_id == parent_user_id,
                ParentStudent.student_id == student_id
            )
        )
    )
    link = link_result.scalars().first()
    if not link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Parent is not linked to this student"
        )
    
    # Remove the link
    await db.delete(link)
    await db.commit()
    
    return {"detail": "Parent unlinked from student successfully"}

@router.get("/students/{student_id}/parents", response_model=List[dict])
async def get_student_parents(
    student_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all parents linked to a student.
    """
    # Check if student exists
    student_result = await db.execute(select(Student).where(Student.id == student_id))
    student = student_result.scalars().first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found"
        )
    
    # Check permissions
    if current_user.role.name != "super_admin":
        # Admin or teacher from the same school
        if current_user.school_id != student.school_id and current_user.role.name not in ["admin_staff", "class_teacher"]:
            # Check if current user is a parent of this student
            parent_result = await db.execute(
                select(ParentStudent).where(
                    and_(
                        ParentStudent.parent_user_id == current_user.id,
                        ParentStudent.student_id == student_id
                    )
                )
            )
            parent_link = parent_result.scalars().first()
            if not parent_link:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to view this student's parents"
                )
    
    # Get all parents linked to this student
    links_result = await db.execute(
        select(ParentStudent).where(ParentStudent.student_id == student_id)
    )
    links = links_result.scalars().all()
    
    # Get parent user data
    parents = []
    for link in links:
        parent_result = await db.execute(select(User).where(User.id == link.parent_user_id))
        parent = parent_result.scalars().first()
        if parent:
            parents.append({
                "id": parent.id,
                "full_name": parent.full_name,
                "email": parent.email,
                "phone": parent.phone,
                "profile_photo_url": parent.profile_photo_url
            })
    
    return parents
