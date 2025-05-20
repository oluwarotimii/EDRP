from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, and_

from app.database import get_db
from app.models.users import User, ParentStudent, Student
from app.models.academics import AcademicSession, Term, StudentAssessmentScore
from app.models.finance import StudentFee, Payment
from app.models.attendance import AttendanceRecord
from app.middleware.authentication import get_current_user

from app.schemas.parents import (
    ParentChildrenResponse,
    ChildSummary,
    ParentChildrenSummaryResponse
)

router = APIRouter()

@router.get("/parents/{parent_id}/children", response_model=ParentChildrenResponse)
async def get_parent_children(
    parent_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all children linked to a parent.
    """
    # Check if the parent exists
    result = await db.execute(select(User).where(User.id == parent_id))
    parent = result.scalars().first()
    
    if not parent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Parent not found"
        )
    
    # Check if the user has permission to view this information
    if current_user.id != parent_id and current_user.role.name not in ["admin", "staff"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this information"
        )
    
    # Get all children linked to the parent
    result = await db.execute(
        select(Student)
        .join(ParentStudent, ParentStudent.student_id == Student.id)
        .where(ParentStudent.parent_user_id == parent_id)
    )
    
    children = result.scalars().all()
    
    return {"children": children}

@router.get("/parents/{parent_id}/summary", response_model=ParentChildrenSummaryResponse)
async def get_parent_children_summary(
    parent_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a summary of all children linked to a parent, including attendance, fees, and academic performance.
    """
    # Check if the parent exists
    result = await db.execute(select(User).where(User.id == parent_id))
    parent = result.scalars().first()
    
    if not parent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Parent not found"
        )
    
    # Check if the user has permission to view this information
    if current_user.id != parent_id and current_user.role.name not in ["admin", "staff"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this information"
        )
    
    # Get all children linked to the parent
    result = await db.execute(
        select(Student)
        .join(ParentStudent, ParentStudent.student_id == Student.id)
        .where(ParentStudent.parent_user_id == parent_id)
    )
    
    children = result.scalars().all()
    children_summaries = []
    
    # Get the current term
    result = await db.execute(
        select(Term)
        .join(AcademicSession)
        .where(AcademicSession.is_current == True)
        .order_by(Term.end_date.desc())
        .limit(1)
    )
    current_term = result.scalars().first()
    
    for child in children:
        # Get attendance information
        result = await db.execute(
            select(func.count(AttendanceRecord.id).label('total'), 
                   func.sum(AttendanceRecord.status == 'present').label('present'))
            .where(AttendanceRecord.student_id == child.id)
            .where(AttendanceRecord.term_id == current_term.id if current_term else None)
        )
        attendance_data = result.first()
        attendance_rate = 0
        if attendance_data and attendance_data.total > 0:
            attendance_rate = (attendance_data.present or 0) / attendance_data.total * 100
        
        # Get fee information
        result = await db.execute(
            select(func.sum(StudentFee.amount_due).label('total_due'),
                   func.sum(Payment.amount).label('total_paid'))
            .outerjoin(Payment, Payment.student_fee_id == StudentFee.id)
            .where(StudentFee.student_id == child.id)
        )
        fee_data = result.first()
        fee_balance = 0
        if fee_data:
            fee_balance = (fee_data.total_due or 0) - (fee_data.total_paid or 0)
        
        # Get academic performance
        result = await db.execute(
            select(func.avg(StudentAssessmentScore.score).label('avg_score'))
            .where(StudentAssessmentScore.student_id == child.id)
            .where(StudentAssessmentScore.term_id == current_term.id if current_term else None)
        )
        performance_data = result.first()
        avg_score = performance_data.avg_score if performance_data else 0
        
        # Get child's class name
        class_name = child.class_.name if child.class_ else "N/A"
        
        # Create child summary
        child_summary = ChildSummary(
            id=child.id,
            name=child.user.full_name,
            class_name=class_name,
            attendance_rate=round(attendance_rate, 2),
            fee_balance=round(fee_balance, 2),
            average_score=round(avg_score, 2) if avg_score else 0
        )
        
        children_summaries.append(child_summary)
    
    return {"children": children_summaries}