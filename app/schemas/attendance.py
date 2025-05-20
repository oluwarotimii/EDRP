from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, Field, validator, condecimal
from enum import Enum


class AttendanceStatusEnum(str, Enum):
    present = "Present"
    absent = "Absent"
    late = "Late"
    excused = "Excused"


# Attendance Record schemas
class AttendanceRecordBase(BaseModel):
    date: date
    status: AttendanceStatusEnum
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class AttendanceRecordCreate(AttendanceRecordBase):
    student_id: int
    class_id: int
    marked_by_user_id: int


class AttendanceRecordUpdate(BaseModel):
    status: Optional[AttendanceStatusEnum] = None
    flagged: Optional[bool] = None
    flagged_reason: Optional[str] = None


class AttendanceRecordInDB(AttendanceRecordBase):
    id: int
    student_id: int
    class_id: int
    marked_by_user_id: int
    flagged: bool
    flagged_reason: Optional[str] = None
    created_at: datetime
    
    class Config:
        orm_mode = True


# Bulk Attendance schemas
class BulkAttendanceRecord(BaseModel):
    student_id: int
    status: AttendanceStatusEnum


class BulkAttendanceCreate(BaseModel):
    class_id: int
    date: date
    marked_by_user_id: int
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    records: List[BulkAttendanceRecord]


# Attendance Statistics
class AttendanceStats(BaseModel):
    total_days: int
    present_days: int
    absent_days: int
    late_days: int
    excused_days: int
    attendance_percentage: float


# GPS Verification
class GPSVerificationRequest(BaseModel):
    latitude: float
    longitude: float
    school_id: int


class GPSVerificationResponse(BaseModel):
    is_valid: bool
    distance: Optional[float] = None
    location_name: Optional[str] = None
    message: str
