from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

class StudentCustomFieldBase(BaseModel):
    field_key: str
    field_value: str

class StudentCustomFieldCreate(StudentCustomFieldBase):
    pass

class StudentCustomFieldUpdate(StudentCustomFieldBase):
    pass

class StudentCustomFieldResponse(StudentCustomFieldBase):
    id: int
    student_id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True