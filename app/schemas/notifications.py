from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
from enum import Enum

class AudienceType(str, Enum):
    SCHOOL = "school"
    CLASS = "class"
    DEPARTMENT = "department"
    USER = "user"

class AnnouncementBase(BaseModel):
    title: str
    message: str
    audience_type: AudienceType
    audience_id: int

class AnnouncementCreate(AnnouncementBase):
    pass

class AnnouncementUpdate(BaseModel):
    title: Optional[str] = None
    message: Optional[str] = None

class AnnouncementResponse(AnnouncementBase):
    id: int
    created_by_user_id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class NotificationBase(BaseModel):
    title: str
    message: str
    related_entity_type: Optional[str] = None
    related_entity_id: Optional[int] = None

class NotificationCreate(NotificationBase):
    user_id: int

class NotificationUpdate(BaseModel):
    is_read: bool = True

class NotificationResponse(NotificationBase):
    id: int
    user_id: int
    is_read: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class NotificationCount(BaseModel):
    total: int
    unread: int