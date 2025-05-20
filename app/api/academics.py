from typing import List, Optional, Dict, Any
from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path, Body, File, UploadFile, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import or_, and_, func, desc, asc, literal_column, case

from app.database import get_db
from app.schemas.academics import (
    AcademicSessionCreate, AcademicSessionUpdate, AcademicSessionInDB,
    TermCreate, TermUpdate, TermInDB,
    AssessmentCreate, AssessmentUpdate, AssessmentInDB,
    StudentAssessmentScoreCreate, StudentAssessmentScoreUpdate, StudentAssessmentScoreInDB,
    ReportCard, SubjectScore
)
from app.models.academics import AcademicSession, Term, Assessment, StudentAssessmentScore
from app.models.users import User, Student, TeacherSubjectClass
from app.models.schools import School, Class, Department, Subject
from app.middleware.authentication import get_current_user, validate_admin_access, RoleChecker

router = APIRouter()

# Role-based access control
allow_academics_management = RoleChecker(["super_admin", "admin_staff", "class_teacher"])
allow_score_management = RoleChecker(["super_admin", "admin_staff", "class_teacher", "subject_teacher"])

# Academic Session endpoints
@router.post("/academic-sessions", response_model=AcademicSessionInDB, status_code=status.HTTP_201_CREATED)
async def create_academic_session(
    session_data: AcademicSessionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new academic session.
    """
    # Check if user has permission
    await validate_admin_access(current_user, db)
    
    # Validate school access
    if current_user.role.name != "super_admin" and current_user.school_id != session_data.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to create sessions for this school"
        )
    
    # Check if session with same name exists for this school
    result = await db.execute(
        select(AcademicSession).where(
            and_(
                AcademicSession.name == session_data.name,
                AcademicSession.school_id == session_data.school_id
            )
        )
    )
    existing_session = result.scalars().first()
    if existing_session:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session with this name already exists for this school"
        )
    
    # Create new session
    db_session = AcademicSession(**session_data.dict())
    db.add(db_session)
    await db.commit()
    await db.refresh(db_session)
    
    return db_session

@router.get("/academic-sessions", response_model=List[AcademicSessionInDB])
async def get_academic_sessions(
    school_id: Optional[int] = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all academic sessions, optionally filtered by school.
    """
    # Build query
    query = select(AcademicSession)
    
    # Filter by school
    if school_id:
        # Check if user has access to this school
        if current_user.role.name != "super_admin" and current_user.school_id != school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view sessions for this school"
            )
        query = query.where(AcademicSession.school_id == school_id)
    elif current_user.role.name != "super_admin":
        # Regular users can only see sessions from their own school
        query = query.where(AcademicSession.school_id == current_user.school_id)
    
    # Sort by start date descending (most recent first)
    query = query.order_by(desc(AcademicSession.start_date))
    
    # Apply pagination
    query = query.offset(skip).limit(limit)
    
    # Execute query
    result = await db.execute(query)
    sessions = result.scalars().all()
    
    return sessions

@router.get("/academic-sessions/{session_id}", response_model=AcademicSessionInDB)
async def get_academic_session(
    session_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific academic session by ID.
    """
    result = await db.execute(select(AcademicSession).where(AcademicSession.id == session_id))
    session = result.scalars().first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Academic session not found"
        )
    
    # Check if user has access to this session's school
    if current_user.role.name != "super_admin" and current_user.school_id != session.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view sessions from another school"
        )
    
    return session

@router.put("/academic-sessions/{session_id}", response_model=AcademicSessionInDB)
async def update_academic_session(
    session_data: AcademicSessionUpdate,
    session_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update an academic session.
    """
    # Check if user has permission
    await validate_admin_access(current_user, db)
    
    # Get session
    result = await db.execute(select(AcademicSession).where(AcademicSession.id == session_id))
    session = result.scalars().first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Academic session not found"
        )
    
    # Check if user has access to this session's school
    if current_user.role.name != "super_admin" and current_user.school_id != session.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update sessions from another school"
        )
    
    # Update session
    update_data = session_data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(session, key, value)
    
    await db.commit()
    await db.refresh(session)
    
    return session

# Term endpoints
@router.post("/terms", response_model=TermInDB, status_code=status.HTTP_201_CREATED)
async def create_term(
    term_data: TermCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new term within an academic session.
    """
    # Check if user has permission
    await validate_admin_access(current_user, db)
    
    # Validate session exists
    session_result = await db.execute(select(AcademicSession).where(AcademicSession.id == term_data.session_id))
    session = session_result.scalars().first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Academic session not found"
        )
    
    # Check if user has access to this session's school
    if current_user.role.name != "super_admin" and current_user.school_id != session.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to create terms for sessions from another school"
        )
    
    # Check if term with same name exists in this session
    term_result = await db.execute(
        select(Term).where(
            and_(
                Term.name == term_data.name,
                Term.session_id == term_data.session_id
            )
        )
    )
    existing_term = term_result.scalars().first()
    if existing_term:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Term with this name already exists in this session"
        )
    
    # Create new term
    db_term = Term(**term_data.dict())
    db.add(db_term)
    await db.commit()
    await db.refresh(db_term)
    
    return db_term

@router.get("/terms", response_model=List[TermInDB])
async def get_terms(
    session_id: Optional[int] = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all terms, optionally filtered by academic session.
    """
    query = select(Term)
    
    # Filter by session
    if session_id:
        query = query.where(Term.session_id == session_id)
        
        # Check if user has access to this session's school
        session_result = await db.execute(select(AcademicSession).where(AcademicSession.id == session_id))
        session = session_result.scalars().first()
        if session and current_user.role.name != "super_admin" and current_user.school_id != session.school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view terms for sessions from another school"
            )
    else:
        # If not filtered by session, join with session to filter by school
        query = query.join(AcademicSession)
        if current_user.role.name != "super_admin":
            query = query.where(AcademicSession.school_id == current_user.school_id)
    
    # Sort by start date
    query = query.order_by(Term.start_date)
    
    # Apply pagination
    query = query.offset(skip).limit(limit)
    
    # Execute query
    result = await db.execute(query)
    terms = result.scalars().all()
    
    return terms

@router.get("/terms/{term_id}", response_model=TermInDB)
async def get_term(
    term_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific term by ID.
    """
    result = await db.execute(select(Term).where(Term.id == term_id))
    term = result.scalars().first()
    
    if not term:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Term not found"
        )
    
    # Check if user has access to this term's session's school
    session_result = await db.execute(select(AcademicSession).where(AcademicSession.id == term.session_id))
    session = session_result.scalars().first()
    
    if current_user.role.name != "super_admin" and current_user.school_id != session.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view terms from another school"
        )
    
    return term

@router.put("/terms/{term_id}", response_model=TermInDB)
async def update_term(
    term_data: TermUpdate,
    term_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update a term.
    """
    # Check if user has permission
    await validate_admin_access(current_user, db)
    
    # Get term
    result = await db.execute(select(Term).where(Term.id == term_id))
    term = result.scalars().first()
    
    if not term:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Term not found"
        )
    
    # Check if user has access to this term's session's school
    session_result = await db.execute(select(AcademicSession).where(AcademicSession.id == term.session_id))
    session = session_result.scalars().first()
    
    if current_user.role.name != "super_admin" and current_user.school_id != session.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update terms from another school"
        )
    
    # Update term
    update_data = term_data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(term, key, value)
    
    await db.commit()
    await db.refresh(term)
    
    return term

# Assessment endpoints
@router.post("/assessments", response_model=AssessmentInDB, status_code=status.HTTP_201_CREATED)
async def create_assessment(
    assessment_data: AssessmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new assessment for a term.
    """
    # Check if user has permission
    if not await allow_academics_management.check_permission(current_user, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to create assessments"
        )
    
    # Validate term exists
    term_result = await db.execute(select(Term).where(Term.id == assessment_data.term_id))
    term = term_result.scalars().first()
    if not term:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Term not found"
        )
    
    # Get session to check school
    session_result = await db.execute(select(AcademicSession).where(AcademicSession.id == term.session_id))
    session = session_result.scalars().first()
    
    # Check if user has access to this school
    if current_user.role.name != "super_admin" and current_user.school_id != assessment_data.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to create assessments for this school"
        )
    
    # Check if the term belongs to the specified school
    if session.school_id != assessment_data.school_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Term does not belong to the specified school"
        )
    
    # Check if assessment with same name exists in this term
    assessment_result = await db.execute(
        select(Assessment).where(
            and_(
                Assessment.name == assessment_data.name,
                Assessment.term_id == assessment_data.term_id
            )
        )
    )
    existing_assessment = assessment_result.scalars().first()
    if existing_assessment:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Assessment with this name already exists in this term"
        )
    
    # Create new assessment
    db_assessment = Assessment(**assessment_data.dict())
    db.add(db_assessment)
    await db.commit()
    await db.refresh(db_assessment)
    
    return db_assessment

@router.get("/assessments", response_model=List[AssessmentInDB])
async def get_assessments(
    school_id: Optional[int] = Query(None),
    term_id: Optional[int] = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all assessments, optionally filtered by school and/or term.
    """
    query = select(Assessment)
    
    # Apply filters
    if school_id:
        # Check if user has access to this school
        if current_user.role.name != "super_admin" and current_user.school_id != school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view assessments for this school"
            )
        query = query.where(Assessment.school_id == school_id)
    elif current_user.role.name != "super_admin":
        # Regular users can only see assessments from their school
        query = query.where(Assessment.school_id == current_user.school_id)
    
    if term_id:
        query = query.where(Assessment.term_id == term_id)
    
    # Apply pagination
    query = query.offset(skip).limit(limit)
    
    # Execute query
    result = await db.execute(query)
    assessments = result.scalars().all()
    
    return assessments

@router.get("/assessments/{assessment_id}", response_model=AssessmentInDB)
async def get_assessment(
    assessment_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific assessment by ID.
    """
    result = await db.execute(select(Assessment).where(Assessment.id == assessment_id))
    assessment = result.scalars().first()
    
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment not found"
        )
    
    # Check if user has access to this assessment's school
    if current_user.role.name != "super_admin" and current_user.school_id != assessment.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view assessments from another school"
        )
    
    return assessment

@router.put("/assessments/{assessment_id}", response_model=AssessmentInDB)
async def update_assessment(
    assessment_data: AssessmentUpdate,
    assessment_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update an assessment.
    """
    # Check if user has permission
    if not await allow_academics_management.check_permission(current_user, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update assessments"
        )
    
    # Get assessment
    result = await db.execute(select(Assessment).where(Assessment.id == assessment_id))
    assessment = result.scalars().first()
    
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment not found"
        )
    
    # Check if user has access to this assessment's school
    if current_user.role.name != "super_admin" and current_user.school_id != assessment.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update assessments from another school"
        )
    
    # Update assessment
    update_data = assessment_data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(assessment, key, value)
    
    await db.commit()
    await db.refresh(assessment)
    
    return assessment

# Student Assessment Score endpoints
@router.post("/scores", response_model=StudentAssessmentScoreInDB, status_code=status.HTTP_201_CREATED)
async def create_student_score(
    score_data: StudentAssessmentScoreCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Record a score for a student in an assessment.
    """
    # Check permission
    if not await allow_score_management.check_permission(current_user, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to record student scores"
        )
    
    # Validate student exists
    student_result = await db.execute(select(Student).where(Student.id == score_data.student_id))
    student = student_result.scalars().first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found"
        )
    
    # Validate assessment exists
    assessment_result = await db.execute(select(Assessment).where(Assessment.id == score_data.assessment_id))
    assessment = assessment_result.scalars().first()
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment not found"
        )
    
    # Validate subject exists
    subject_result = await db.execute(select(Subject).where(Subject.id == score_data.subject_id))
    subject = subject_result.scalars().first()
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subject not found"
        )
    
    # Check if user has access to student's school
    if current_user.role.name != "super_admin" and current_user.school_id != student.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to record scores for students from another school"
        )
    
    # Check if subject teacher has permission to record scores for this subject/class
    if current_user.role.name == "subject_teacher":
        # Check if teacher is assigned to this subject and student's class
        if student.class_id:
            teacher_assignment_result = await db.execute(
                select(TeacherSubjectClass).where(
                    and_(
                        TeacherSubjectClass.teacher_user_id == current_user.id,
                        TeacherSubjectClass.subject_id == score_data.subject_id,
                        TeacherSubjectClass.class_id == student.class_id
                    )
                )
            )
            assignment = teacher_assignment_result.scalars().first()
            if not assignment:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to record scores for this subject and class"
                )
    
    # Check if score is within the allowed range (0 to max_score)
    if float(score_data.score) > float(assessment.max_score):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Score cannot exceed the maximum score ({assessment.max_score})"
        )
    
    # Check if score already exists
    existing_result = await db.execute(
        select(StudentAssessmentScore).where(
            and_(
                StudentAssessmentScore.student_id == score_data.student_id,
                StudentAssessmentScore.assessment_id == score_data.assessment_id,
                StudentAssessmentScore.subject_id == score_data.subject_id
            )
        )
    )
    existing_score = existing_result.scalars().first()
    if existing_score:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Score already exists for this student, assessment, and subject"
        )
    
    # Create new score
    db_score = StudentAssessmentScore(**score_data.dict())
    db.add(db_score)
    await db.commit()
    await db.refresh(db_score)
    
    return db_score

@router.post("/scores/batch", response_model=List[StudentAssessmentScoreInDB], status_code=status.HTTP_201_CREATED)
async def create_batch_scores(
    scores: List[StudentAssessmentScoreCreate],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Record multiple scores in a batch operation.
    """
    # Check permission
    if not await allow_score_management.check_permission(current_user, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to record student scores"
        )
    
    if not scores:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No scores provided"
        )
    
    # Validate that all scores are for the same assessment and subject
    assessment_id = scores[0].assessment_id
    subject_id = scores[0].subject_id
    
    if not all(score.assessment_id == assessment_id and score.subject_id == subject_id for score in scores):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="All scores in a batch must be for the same assessment and subject"
        )
    
    # Validate assessment exists
    assessment_result = await db.execute(select(Assessment).where(Assessment.id == assessment_id))
    assessment = assessment_result.scalars().first()
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment not found"
        )
    
    # Validate subject exists
    subject_result = await db.execute(select(Subject).where(Subject.id == subject_id))
    subject = subject_result.scalars().first()
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subject not found"
        )
    
    # Get all students in one query
    student_ids = [score.student_id for score in scores]
    students_result = await db.execute(select(Student).where(Student.id.in_(student_ids)))
    students = {student.id: student for student in students_result.scalars().all()}
    
    # Check if any students are missing
    missing_student_ids = set(student_ids) - set(students.keys())
    if missing_student_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Some students not found: {missing_student_ids}"
        )
    
    # Check if user has access to all students' schools
    if current_user.role.name != "super_admin":
        for student in students.values():
            if student.school_id != current_user.school_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Not authorized to record scores for student {student.id} from another school"
                )
    
    # Check if subject teacher has permission to record scores for this subject/class
    if current_user.role.name == "subject_teacher":
        class_ids = {student.class_id for student in students.values() if student.class_id is not None}
        
        for class_id in class_ids:
            teacher_assignment_result = await db.execute(
                select(TeacherSubjectClass).where(
                    and_(
                        TeacherSubjectClass.teacher_user_id == current_user.id,
                        TeacherSubjectClass.subject_id == subject_id,
                        TeacherSubjectClass.class_id == class_id
                    )
                )
            )
            assignment = teacher_assignment_result.scalars().first()
            if not assignment:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Not authorized to record scores for subject {subject_id} and class {class_id}"
                )
    
    # Check max score for all scores
    for score in scores:
        if float(score.score) > float(assessment.max_score):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Score for student {score.student_id} exceeds the maximum score ({assessment.max_score})"
            )
    
    # Check for existing scores and create new ones
    created_scores = []
    
    for score_data in scores:
        # Check if score already exists
        existing_result = await db.execute(
            select(StudentAssessmentScore).where(
                and_(
                    StudentAssessmentScore.student_id == score_data.student_id,
                    StudentAssessmentScore.assessment_id == score_data.assessment_id,
                    StudentAssessmentScore.subject_id == score_data.subject_id
                )
            )
        )
        existing_score = existing_result.scalars().first()
        
        if existing_score:
            # Update existing score
            existing_score.score = score_data.score
            created_scores.append(existing_score)
        else:
            # Create new score
            db_score = StudentAssessmentScore(**score_data.dict())
            db.add(db_score)
            created_scores.append(db_score)
    
    await db.commit()
    
    # Refresh all scores to get updated values
    for score in created_scores:
        await db.refresh(score)
    
    return created_scores

@router.get("/scores", response_model=List[StudentAssessmentScoreInDB])
async def get_student_scores(
    student_id: Optional[int] = Query(None),
    assessment_id: Optional[int] = Query(None),
    subject_id: Optional[int] = Query(None),
    class_id: Optional[int] = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get student assessment scores with optional filtering.
    """
    # Start with base query
    query = select(StudentAssessmentScore)
    
    # Join with Student to filter by class and check school permissions
    if class_id or current_user.role.name != "super_admin":
        query = query.join(Student, StudentAssessmentScore.student_id == Student.id)
    
    # Apply filters
    if student_id:
        query = query.where(StudentAssessmentScore.student_id == student_id)
        
        # Check if user has access to this student
        student_result = await db.execute(select(Student).where(Student.id == student_id))
        student = student_result.scalars().first()
        
        if student and current_user.role.name != "super_admin" and student.school_id != current_user.school_id:
            # Check if current user is a parent of this student
            is_parent = False
            if current_user.role.name == "parent":
                parent_student_result = await db.execute(
                    select(User).join(
                        "student_parents",
                        User.id == student.id
                    ).where(User.id == current_user.id)
                )
                is_parent = parent_student_result.scalars().first() is not None
            
            if not is_parent:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to view scores for students from another school"
                )
    
    if assessment_id:
        query = query.where(StudentAssessmentScore.assessment_id == assessment_id)
    
    if subject_id:
        query = query.where(StudentAssessmentScore.subject_id == subject_id)
    
    if class_id:
        query = query.where(Student.class_id == class_id)
    
    # Filter by school for regular users
    if current_user.role.name != "super_admin":
        query = query.where(Student.school_id == current_user.school_id)
    
    # Apply pagination
    query = query.offset(skip).limit(limit)
    
    # Execute query
    result = await db.execute(query)
    scores = result.scalars().all()
    
    return scores

@router.put("/scores/{score_id}", response_model=StudentAssessmentScoreInDB)
async def update_student_score(
    score_data: StudentAssessmentScoreUpdate,
    score_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update a student's assessment score.
    """
    # Check permission
    if not await allow_score_management.check_permission(current_user, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update student scores"
        )
    
    # Get score
    score_result = await db.execute(select(StudentAssessmentScore).where(StudentAssessmentScore.id == score_id))
    score = score_result.scalars().first()
    
    if not score:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Score record not found"
        )
    
    # Get student to check school
    student_result = await db.execute(select(Student).where(Student.id == score.student_id))
    student = student_result.scalars().first()
    
    # Check if user has access to student's school
    if current_user.role.name != "super_admin" and current_user.school_id != student.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update scores for students from another school"
        )
    
    # Check if subject teacher has permission to update scores for this subject/class
    if current_user.role.name == "subject_teacher":
        if student.class_id:
            teacher_assignment_result = await db.execute(
                select(TeacherSubjectClass).where(
                    and_(
                        TeacherSubjectClass.teacher_user_id == current_user.id,
                        TeacherSubjectClass.subject_id == score.subject_id,
                        TeacherSubjectClass.class_id == student.class_id
                    )
                )
            )
            assignment = teacher_assignment_result.scalars().first()
            if not assignment:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to update scores for this subject and class"
                )
    
    # Get assessment to check max score
    assessment_result = await db.execute(select(Assessment).where(Assessment.id == score.assessment_id))
    assessment = assessment_result.scalars().first()
    
    # Check if score is within the allowed range
    if float(score_data.score) > float(assessment.max_score):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Score cannot exceed the maximum score ({assessment.max_score})"
        )
    
    # Update score
    score.score = score_data.score
    await db.commit()
    await db.refresh(score)
    
    return score

@router.get("/reports/student/{student_id}/term/{term_id}", response_model=ReportCard)
async def get_student_report_card(
    student_id: int = Path(..., gt=0),
    term_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Generate a report card for a student for a specific term.
    """
    # Verify student exists
    student_result = await db.execute(select(Student).where(Student.id == student_id))
    student = student_result.scalars().first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found"
        )
    
    # Check if user has access to student's school
    if current_user.role.name != "super_admin" and current_user.school_id != student.school_id:
        # Check if the current user is a parent of this student
        is_parent = False
        if current_user.role.name == "parent":
            parent_student_result = await db.execute(
                select(User).join(
                    "student_parents",
                    User.id == student.id
                ).where(User.id == current_user.id)
            )
            is_parent = parent_student_result.scalars().first() is not None
        
        if not is_parent:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view report card for students from another school"
            )
    
    # Verify term exists
    term_result = await db.execute(select(Term).where(Term.id == term_id))
    term = term_result.scalars().first()
    if not term:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Term not found"
        )
    
    # Get student's class
    if not student.class_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student is not assigned to a class"
        )
    
    class_result = await db.execute(select(Class).where(Class.id == student.class_id))
    class_ = class_result.scalars().first()
    
    # Get academic session
    session_result = await db.execute(select(AcademicSession).where(AcademicSession.id == term.session_id))
    session = session_result.scalars().first()
    
    # Get student's user info
    user_result = await db.execute(select(User).where(User.id == student.user_id))
    user = user_result.scalars().first()
    
    # Get all assessments for this term
    assessments_result = await db.execute(
        select(Assessment).where(Assessment.term_id == term_id)
    )
    assessments = assessments_result.scalars().all()
    assessment_dict = {assessment.id: assessment for assessment in assessments}
    
    # Get all subjects for student's class/department
    subjects_query = select(Subject)
    if student.department_id:
        subjects_query = subjects_query.where(
            or_(
                Subject.department_id == student.department_id,
                Subject.department_id == None
            )
        )
    
    subjects_result = await db.execute(subjects_query)
    subjects = subjects_result.scalars().all()
    
    # Get all scores for this student in this term
    scores_result = await db.execute(
        select(StudentAssessmentScore).where(
            and_(
                StudentAssessmentScore.student_id == student_id,
                StudentAssessmentScore.assessment_id.in_([a.id for a in assessments])
            )
        )
    )
    all_scores = scores_result.scalars().all()
    
    # Organize scores by subject
    subject_scores = {}
    for subject in subjects:
        subject_scores[subject.id] = {
            "subject_id": subject.id,
            "subject_name": subject.name,
            "scores": [],
            "total": 0,
            "average": 0,
            "grade": "N/A"
        }
    
    # Process all scores
    for score in all_scores:
        if score.subject_id in subject_scores:
            assessment = assessment_dict.get(score.assessment_id)
            if assessment:
                subject_scores[score.subject_id]["scores"].append({
                    "assessment_id": score.assessment_id,
                    "assessment_name": assessment.name,
                    "max_score": float(assessment.max_score),
                    "score": float(score.score)
                })
    
    # Calculate totals, averages, and grades for each subject
    subjects_with_scores = []
    overall_total = 0
    total_possible = 0
    subjects_count = 0
    
    for subject_id, data in subject_scores.items():
        if data["scores"]:  # Only include subjects with scores
            total_score = sum(s["score"] for s in data["scores"])
            max_possible = sum(s["max_score"] for s in data["scores"])
            data["total"] = total_score
            
            if max_possible > 0:
                # Calculate percentage
                percentage = (total_score / max_possible) * 100
                data["average"] = round(percentage, 2)
                
                # Assign grade based on percentage
                if percentage >= 80:
                    data["grade"] = "A"
                elif percentage >= 70:
                    data["grade"] = "B"
                elif percentage >= 60:
                    data["grade"] = "C"
                elif percentage >= 50:
                    data["grade"] = "D"
                elif percentage >= 40:
                    data["grade"] = "E"
                else:
                    data["grade"] = "F"
                
                overall_total += percentage
                subjects_count += 1
            
            subjects_with_scores.append(data)
    
    # Calculate overall average and grade
    overall_average = overall_total / subjects_count if subjects_count > 0 else 0
    overall_grade = "N/A"
    
    if subjects_count > 0:
        if overall_average >= 80:
            overall_grade = "A"
        elif overall_average >= 70:
            overall_grade = "B"
        elif overall_average >= 60:
            overall_grade = "C"
        elif overall_average >= 50:
            overall_grade = "D"
        elif overall_average >= 40:
            overall_grade = "E"
        else:
            overall_grade = "F"
    
    # Sort subjects by average score (descending)
    subjects_with_scores.sort(key=lambda x: x["average"], reverse=True)
    
    return {
        "student_id": student_id,
        "student_name": user.full_name,
        "class_id": student.class_id,
        "class_name": class_.name if class_ else "N/A",
        "term_id": term_id,
        "term_name": term.name,
        "session_id": session.id,
        "session_name": session.name,
        "subjects": subjects_with_scores,
        "overall_average": round(overall_average, 2),
        "overall_grade": overall_grade,
        "position": None,  # Need to calculate class ranking separately
        "teacher_comment": None,
        "principal_comment": None
    }
