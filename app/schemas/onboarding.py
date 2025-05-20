from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime

# School registration schemas
class AdminRegistration(BaseModel):
    name: str
    email: EmailStr
    password: str = Field(..., min_length=8)

class SchoolRegistration(BaseModel):
    school_name: str
    admin: AdminRegistration

class SchoolRegistrationResponse(BaseModel):
    id: int
    name: str
    join_code: str
    code_expires_at: datetime

# Staff join schemas
class JoinSchoolRequest(BaseModel):
    join_code: str = Field(..., min_length=5, max_length=5)
    name: str
    email: EmailStr
    password: str = Field(..., min_length=8)

class JoinSchoolResponse(BaseModel):
    message: str
    user_id: int

# User approval schemas
class UserApprovalAction(BaseModel):
    action: str = Field(..., pattern="^(approve|reject)$")

class PendingUserResponse(BaseModel):
    id: int
    full_name: str
    email: EmailStr
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True

# Join code regeneration schemas
class RegenerateCodeResponse(BaseModel):
    join_code: str
    code_expires_at: datetime