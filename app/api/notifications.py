from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Path, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, and_, or_, desc

from app.database import get_db
from app.models.users import User, Student
from app.models.schools import School, Class, Department
from app.models.notifications import Announcement, Notification, AudienceType
from app.middleware.authentication import get_current_user
from app.schemas.notifications import (
    AnnouncementCreate, 
    AnnouncementUpdate, 
    AnnouncementResponse, 
    NotificationCreate, 
    NotificationUpdate, 
    NotificationResponse,
    NotificationCount
)

router = APIRouter()

@router.post("/announcements", response_model=AnnouncementResponse)
async def create_announcement(
    announcement_data: AnnouncementCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new announcement for a school, class, department, or specific user.
    """
    # Validate audience exists
    if announcement_data.audience_type == AudienceType.SCHOOL:
        result = await db.execute(select(School).where(School.id == announcement_data.audience_id))
        if not result.scalars().first():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="School not found")
    elif announcement_data.audience_type == AudienceType.CLASS:
        result = await db.execute(select(Class).where(Class.id == announcement_data.audience_id))
        if not result.scalars().first():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")
    elif announcement_data.audience_type == AudienceType.DEPARTMENT:
        result = await db.execute(select(Department).where(Department.id == announcement_data.audience_id))
        if not result.scalars().first():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
    elif announcement_data.audience_type == AudienceType.USER:
        result = await db.execute(select(User).where(User.id == announcement_data.audience_id))
        if not result.scalars().first():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    # Create announcement
    new_announcement = Announcement(
        title=announcement_data.title,
        message=announcement_data.message,
        created_by_user_id=current_user.id,
        audience_type=announcement_data.audience_type,
        audience_id=announcement_data.audience_id
    )
    
    db.add(new_announcement)
    await db.commit()
    await db.refresh(new_announcement)
    
    # Create notifications for users based on audience
    await create_notifications_from_announcement(db, new_announcement)
    
    return new_announcement

async def create_notifications_from_announcement(db: AsyncSession, announcement: Announcement):
    """
    Create notifications for users based on the announcement audience type.
    """
    user_ids = []
    
    # Get users based on audience type
    if announcement.audience_type == AudienceType.SCHOOL:
        result = await db.execute(select(User.id).where(User.school_id == announcement.audience_id))
        user_ids = [row[0] for row in result.all()]
    
    elif announcement.audience_type == AudienceType.CLASS:
        result = await db.execute(
            select(User.id)
            .join(Student, Student.user_id == User.id)
            .where(Student.class_id == announcement.audience_id)
        )
        user_ids = [row[0] for row in result.all()]
    
    elif announcement.audience_type == AudienceType.DEPARTMENT:
        result = await db.execute(
            select(User.id)
            .join(Student, Student.user_id == User.id)
            .where(Student.department_id == announcement.audience_id)
        )
        user_ids = [row[0] for row in result.all()]
    
    elif announcement.audience_type == AudienceType.USER:
        user_ids = [announcement.audience_id]
    
    # Create notifications for each user
    for user_id in user_ids:
        notification = Notification(
            user_id=user_id,
            title=announcement.title,
            message=announcement.message,
            related_entity_type="announcement",
            related_entity_id=announcement.id
        )
        db.add(notification)
    
    await db.commit()

@router.get("/announcements", response_model=List[AnnouncementResponse])
async def get_announcements(
    audience_type: Optional[AudienceType] = None,
    audience_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all announcements, optionally filtered by audience type and ID.
    """
    query = select(Announcement).order_by(desc(Announcement.created_at))
    
    # Apply filters if provided
    if audience_type:
        query = query.where(Announcement.audience_type == audience_type)
    
    if audience_id:
        query = query.where(Announcement.audience_id == audience_id)
    
    # Add pagination
    query = query.offset(skip).limit(limit)
    
    result = await db.execute(query)
    announcements = result.scalars().all()
    
    return announcements

@router.get("/announcements/{announcement_id}", response_model=AnnouncementResponse)
async def get_announcement(
    announcement_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific announcement by ID.
    """
    result = await db.execute(select(Announcement).where(Announcement.id == announcement_id))
    announcement = result.scalars().first()
    
    if not announcement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Announcement not found"
        )
    
    return announcement

@router.put("/announcements/{announcement_id}", response_model=AnnouncementResponse)
async def update_announcement(
    announcement_data: AnnouncementUpdate,
    announcement_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update an announcement.
    """
    result = await db.execute(select(Announcement).where(Announcement.id == announcement_id))
    announcement = result.scalars().first()
    
    if not announcement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Announcement not found"
        )
    
    # Check if user is authorized (created the announcement or is admin)
    if announcement.created_by_user_id != current_user.id and current_user.role.name != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this announcement"
        )
    
    # Update fields
    if announcement_data.title is not None:
        announcement.title = announcement_data.title
    
    if announcement_data.message is not None:
        announcement.message = announcement_data.message
    
    await db.commit()
    await db.refresh(announcement)
    
    return announcement

@router.delete("/announcements/{announcement_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_announcement(
    announcement_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete an announcement.
    """
    result = await db.execute(select(Announcement).where(Announcement.id == announcement_id))
    announcement = result.scalars().first()
    
    if not announcement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Announcement not found"
        )
    
    # Check if user is authorized (created the announcement or is admin)
    if announcement.created_by_user_id != current_user.id and current_user.role.name != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this announcement"
        )
    
    await db.delete(announcement)
    await db.commit()

@router.post("/notifications", response_model=NotificationResponse)
async def create_notification(
    notification_data: NotificationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new notification for a user.
    """
    # Check if user exists
    result = await db.execute(select(User).where(User.id == notification_data.user_id))
    user = result.scalars().first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Create notification
    new_notification = Notification(
        user_id=notification_data.user_id,
        title=notification_data.title,
        message=notification_data.message,
        related_entity_type=notification_data.related_entity_type,
        related_entity_id=notification_data.related_entity_id
    )
    
    db.add(new_notification)
    await db.commit()
    await db.refresh(new_notification)
    
    return new_notification

@router.get("/notifications/user/{user_id}", response_model=List[NotificationResponse])
async def get_user_notifications(
    user_id: int = Path(..., gt=0),
    unread_only: bool = Query(False),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get notifications for a specific user.
    """
    # Check authorization (user can only view their own notifications unless admin)
    if current_user.id != user_id and current_user.role.name != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view these notifications"
        )
    
    # Build query
    query = select(Notification).where(Notification.user_id == user_id)
    
    if unread_only:
        query = query.where(Notification.is_read == False)
    
    query = query.order_by(desc(Notification.created_at)).offset(skip).limit(limit)
    
    result = await db.execute(query)
    notifications = result.scalars().all()
    
    return notifications

@router.put("/notifications/{notification_id}/mark-read", response_model=NotificationResponse)
async def mark_notification_as_read(
    notification_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Mark a notification as read.
    """
    result = await db.execute(select(Notification).where(Notification.id == notification_id))
    notification = result.scalars().first()
    
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
    
    # Check authorization (user can only update their own notifications)
    if notification.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this notification"
        )
    
    # Mark as read
    notification.is_read = True
    
    await db.commit()
    await db.refresh(notification)
    
    return notification

@router.get("/notifications/user/{user_id}/count", response_model=NotificationCount)
async def get_notification_count(
    user_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get the count of total and unread notifications for a user.
    """
    # Check authorization (user can only view their own notification count unless admin)
    if current_user.id != user_id and current_user.role.name != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this information"
        )
    
    # Get total count
    result = await db.execute(
        select(func.count(Notification.id))
        .where(Notification.user_id == user_id)
    )
    total_count = result.scalar_one()
    
    # Get unread count
    result = await db.execute(
        select(func.count(Notification.id))
        .where(and_(
            Notification.user_id == user_id,
            Notification.is_read == False
        ))
    )
    unread_count = result.scalar_one()
    
    return {"total": total_count, "unread": unread_count}