from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

class StudentBase(BaseModel):
    admission_number: str
    date_of_birth: datetime
    gender: str
    class_id: Optional[int] = None
    department_id: Optional[int] = None
    session_id: Optional[int] = None
    photo_url: Optional[str] = None

class StudentCreate(StudentBase):
    user_id: int
    school_id: int

class StudentUpdate(StudentBase):
    pass

class StudentResponse(BaseModel):
    id: int
    user_id: int
    school_id: int
    admission_number: str
    date_of_birth: datetime
    gender: str
    class_id: Optional[int] = None
    department_id: Optional[int] = None
    session_id: Optional[int] = None
    photo_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True