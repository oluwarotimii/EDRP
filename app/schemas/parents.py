from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from app.schemas.students import StudentResponse

class ParentStudentCreate(BaseModel):
    parent_user_id: int
    student_id: int

class ParentStudentResponse(BaseModel):
    parent_user_id: int
    student_id: int
    
    class Config:
        from_attributes = True

class ParentChildrenResponse(BaseModel):
    children: List[StudentResponse]

class ChildSummary(BaseModel):
    id: int
    name: str
    class_name: str
    attendance_rate: float
    fee_balance: float
    average_score: float

class ParentChildrenSummaryResponse(BaseModel):
    children: List[ChildSummary]