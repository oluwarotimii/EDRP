from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import or_, and_, func, desc, asc

from app.database import get_db
from app.schemas.communication import (
    MessageCreate, MessageUpdate, MessageInDB,
    BehaviorReportCreate, BehaviorReportUpdate, BehaviorReportInDB,
    AuditLogCreate, AuditLogInDB, NotificationCreate, NotificationInDB
)
from app.models.users import User, Student
from app.models.communication import Message, BehaviorReport, AuditLog
from app.middleware.authentication import get_current_user, validate_admin_access, RoleChecker

router = APIRouter()

# Role-based access control
allow_behavior_reports = RoleChecker(["super_admin", "admin_staff", "class_teacher", "subject_teacher"])

# Message endpoints
@router.post("/messages", response_model=MessageInDB, status_code=status.HTTP_201_CREATED)
async def create_message(
    message_data: MessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Send a new message.
    """
    # Ensure sender is the current user
    if message_data.sender_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only send messages as yourself"
        )
    
    # Verify receiver exists
    receiver_result = await db.execute(select(User).where(User.id == message_data.receiver_user_id))
    receiver = receiver_result.scalars().first()
    if not receiver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipient not found"
        )
    
    # Check if users are from the same school (except for super_admin)
    if current_user.role.name != "super_admin" and current_user.school_id != receiver.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only message users from your school"
        )
    
    # Create message
    db_message = Message(**message_data.dict())
    db.add(db_message)
    await db.commit()
    await db.refresh(db_message)
    
    return db_message

@router.get("/messages", response_model=List[MessageInDB])
async def get_messages(
    with_user_id: Optional[int] = Query(None, description="User ID to filter conversations"),
    unread_only: bool = Query(False, description="Filter to only unread messages"),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get messages for the current user, optionally filtered by conversation partner.
    """
    # Base query for messages sent to or by the current user
    query = select(Message).where(
        or_(
            Message.sender_user_id == current_user.id,
            Message.receiver_user_id == current_user.id
        )
    )
    
    # Filter by conversation partner
    if with_user_id:
        query = query.where(
            or_(
                and_(
                    Message.sender_user_id == current_user.id,
                    Message.receiver_user_id == with_user_id
                ),
                and_(
                    Message.sender_user_id == with_user_id,
                    Message.receiver_user_id == current_user.id
                )
            )
        )
    
    # Filter for unread messages
    if unread_only:
        query = query.where(
            and_(
                Message.receiver_user_id == current_user.id,
                Message.read_at == None
            )
        )
    
    # Order by timestamp (newest first)
    query = query.order_by(desc(Message.created_at))
    
    # Apply pagination
    query = query.offset(skip).limit(limit)
    
    # Execute query
    result = await db.execute(query)
    messages = result.scalars().all()
    
    return messages

@router.put("/messages/{message_id}/read", response_model=MessageInDB)
async def mark_message_as_read(
    message_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Mark a message as read.
    """
    # Get the message
    result = await db.execute(select(Message).where(Message.id == message_id))
    message = result.scalars().first()
    
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found"
        )
    
    # Ensure the current user is the recipient
    if message.receiver_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only mark messages sent to you as read"
        )
    
    # Mark as read
    message.read_at = datetime.now()
    await db.commit()
    await db.refresh(message)
    
    return message

@router.get("/messages/unread-count", response_model=dict)
async def get_unread_message_count(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get the count of unread messages for the current user.
    """
    query = select(func.count()).select_from(Message).where(
        and_(
            Message.receiver_user_id == current_user.id,
            Message.read_at == None
        )
    )
    
    result = await db.execute(query)
    count = result.scalar()
    
    return {"unread_count": count}

# Behavior Report endpoints
@router.post("/behavior-reports", response_model=BehaviorReportInDB, status_code=status.HTTP_201_CREATED)
async def create_behavior_report(
    report_data: BehaviorReportCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new behavior report for a student.
    """
    # Check if user has permission to create behavior reports
    if not await allow_behavior_reports.check_permission(current_user, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to create behavior reports"
        )
    
    # Ensure reported_by is the current user
    if report_data.reported_by_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only create reports as yourself"
        )
    
    # Validate student exists
    student_result = await db.execute(select(Student).where(Student.id == report_data.student_id))
    student = student_result.scalars().first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found"
        )
    
    # Check if user has access to student's school
    if current_user.role.name != "super_admin" and current_user.school_id != student.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to create reports for students from another school"
        )
    
    # Create behavior report
    db_report = BehaviorReport(**report_data.dict())
    db.add(db_report)
    await db.commit()
    await db.refresh(db_report)
    
    # Log the action
    audit_log = AuditLog(
        user_id=current_user.id,
        action="create_behavior_report",
        entity_type="behavior_report",
        entity_id=db_report.id
    )
    db.add(audit_log)
    await db.commit()
    
    return db_report

@router.get("/behavior-reports", response_model=List[BehaviorReportInDB])
async def get_behavior_reports(
    student_id: Optional[int] = Query(None),
    reported_by_user_id: Optional[int] = Query(None),
    behavior_type: Optional[str] = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get behavior reports with optional filtering.
    """
    # Build base query
    query = select(BehaviorReport)
    
    # Apply filters
    if student_id:
        query = query.where(BehaviorReport.student_id == student_id)
        
        # Check permissions for viewing student's reports
        student_result = await db.execute(select(Student).where(Student.id == student_id))
        student = student_result.scalars().first()
        
        if student:
            if current_user.role.name != "super_admin" and current_user.school_id != student.school_id:
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
                        detail="Not authorized to view reports for students from another school"
                    )
    
    if reported_by_user_id:
        query = query.where(BehaviorReport.reported_by_user_id == reported_by_user_id)
    
    if behavior_type:
        query = query.where(BehaviorReport.behavior_type == behavior_type)
    
    # Filter by school for regular users if no specific student is requested
    if not student_id and current_user.role.name != "super_admin":
        query = query.join(Student, BehaviorReport.student_id == Student.id)
        query = query.where(Student.school_id == current_user.school_id)
    
    # Order by report date (newest first)
    query = query.order_by(desc(BehaviorReport.report_date))
    
    # Apply pagination
    query = query.offset(skip).limit(limit)
    
    # Execute query
    result = await db.execute(query)
    reports = result.scalars().all()
    
    return reports

@router.get("/behavior-reports/{report_id}", response_model=BehaviorReportInDB)
async def get_behavior_report(
    report_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific behavior report by ID.
    """
    result = await db.execute(select(BehaviorReport).where(BehaviorReport.id == report_id))
    report = result.scalars().first()
    
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Behavior report not found"
        )
    
    # Check permissions
    student_result = await db.execute(select(Student).where(Student.id == report.student_id))
    student = student_result.scalars().first()
    
    if current_user.role.name != "super_admin" and current_user.school_id != student.school_id:
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
        
        if not is_parent and current_user.id != report.reported_by_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view this behavior report"
            )
    
    return report

@router.put("/behavior-reports/{report_id}", response_model=BehaviorReportInDB)
async def update_behavior_report(
    report_data: BehaviorReportUpdate,
    report_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update a behavior report.
    """
    # Get the report
    result = await db.execute(select(BehaviorReport).where(BehaviorReport.id == report_id))
    report = result.scalars().first()
    
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Behavior report not found"
        )
    
    # Check if user has permission to update the report
    if current_user.role.name not in ["super_admin", "admin_staff"]:
        # Regular teachers can only update their own reports
        if current_user.id != report.reported_by_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only update your own behavior reports"
            )
    
    # Check school access
    student_result = await db.execute(select(Student).where(Student.id == report.student_id))
    student = student_result.scalars().first()
    
    if current_user.role.name != "super_admin" and current_user.school_id != student.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update reports for students from another school"
        )
    
    # Update report
    update_data = report_data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(report, key, value)
    
    await db.commit()
    await db.refresh(report)
    
    # Log the action
    audit_log = AuditLog(
        user_id=current_user.id,
        action="update_behavior_report",
        entity_type="behavior_report",
        entity_id=report.id
    )
    db.add(audit_log)
    await db.commit()
    
    return report

# Audit Log endpoints
@router.get("/audit-logs", response_model=List[AuditLogInDB])
async def get_audit_logs(
    user_id: Optional[int] = Query(None),
    entity_type: Optional[str] = Query(None),
    entity_id: Optional[int] = Query(None),
    action: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get audit logs with optional filtering (admin only).
    """
    # Check if user has permission to view audit logs
    await validate_admin_access(current_user, db)
    
    # Build base query
    query = select(AuditLog)
    
    # Apply filters
    if user_id:
        query = query.where(AuditLog.user_id == user_id)
    
    if entity_type:
        query = query.where(AuditLog.entity_type == entity_type)
    
    if entity_id:
        query = query.where(AuditLog.entity_id == entity_id)
    
    if action:
        query = query.where(AuditLog.action == action)
    
    if start_date:
        query = query.where(AuditLog.timestamp >= start_date)
    
    if end_date:
        query = query.where(AuditLog.timestamp <= end_date)
    
    # School-specific filtering for non-super admins
    if current_user.role.name != "super_admin":
        # Join with users to filter by school_id
        query = query.join(User, AuditLog.user_id == User.id, isouter=True)
        query = query.where(or_(User.school_id == current_user.school_id, AuditLog.user_id == None))
    
    # Order by timestamp (newest first)
    query = query.order_by(desc(AuditLog.timestamp))
    
    # Apply pagination
    query = query.offset(skip).limit(limit)
    
    # Execute query
    result = await db.execute(query)
    logs = result.scalars().all()
    
    return logs

# Internal function to create audit logs
async def create_audit_log(
    db: AsyncSession,
    user_id: Optional[int],
    action: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    ip_address: Optional[str] = None
):
    """
    Create an audit log entry.
    """
    audit_log = AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        ip_address=ip_address
    )
    db.add(audit_log)
    await db.commit()
    
    return audit_log
