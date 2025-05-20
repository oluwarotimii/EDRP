from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, validator, HttpUrl
from enum import Enum


# Message schemas
class MessageBase(BaseModel):
    content: str
    attachment_url: Optional[str] = None
    is_group_message: bool = False


class MessageCreate(MessageBase):
    sender_user_id: int
    receiver_user_id: int


class MessageUpdate(BaseModel):
    read_at: Optional[datetime] = None


class MessageInDB(MessageBase):
    id: int
    sender_user_id: int
    receiver_user_id: int
    created_at: datetime
    read_at: Optional[datetime] = None
    
    class Config:
        orm_mode = True


# Behavior Report schemas
class BehaviorReportBase(BaseModel):
    behavior_type: str
    description: Optional[str] = None
    action_taken: Optional[str] = None


class BehaviorReportCreate(BehaviorReportBase):
    student_id: int
    reported_by_user_id: int


class BehaviorReportUpdate(BaseModel):
    behavior_type: Optional[str] = None
    description: Optional[str] = None
    action_taken: Optional[str] = None


class BehaviorReportInDB(BehaviorReportBase):
    id: int
    student_id: int
    reported_by_user_id: int
    report_date: datetime
    created_at: datetime
    
    class Config:
        orm_mode = True


# Audit Log schemas
class AuditLogBase(BaseModel):
    action: str
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    ip_address: Optional[str] = None


class AuditLogCreate(AuditLogBase):
    user_id: Optional[int] = None


class AuditLogInDB(AuditLogBase):
    id: int
    user_id: Optional[int] = None
    timestamp: datetime
    
    class Config:
        orm_mode = True


# Notification schemas
class NotificationType(str, Enum):
    attendance = "attendance"
    behavior = "behavior"
    fee = "fee"
    academic = "academic"
    general = "general"


class NotificationBase(BaseModel):
    title: str
    message: str
    type: NotificationType
    is_read: bool = False
    link: Optional[str] = None


class NotificationCreate(NotificationBase):
    recipient_id: int
    sender_id: Optional[int] = None


class NotificationInDB(NotificationBase):
    id: int
    recipient_id: int
    sender_id: Optional[int] = None
    created_at: datetime
    read_at: Optional[datetime] = None
    
    class Config:
        orm_mode = True
