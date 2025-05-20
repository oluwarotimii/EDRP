from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field, validator
from enum import Enum


# Role schemas
class RoleBase(BaseModel):
    name: str
    description: Optional[str] = None


class RoleCreate(RoleBase):
    pass


class RoleUpdate(RoleBase):
    name: Optional[str] = None


class RoleInDB(RoleBase):
    id: int
    
    class Config:
        orm_mode = True


# Permission schemas
class PermissionBase(BaseModel):
    name: str
    description: Optional[str] = None


class PermissionCreate(PermissionBase):
    pass


class PermissionUpdate(PermissionBase):
    name: Optional[str] = None


class PermissionInDB(PermissionBase):
    id: int
    
    class Config:
        orm_mode = True


# User schemas
class UserBase(BaseModel):
    full_name: str
    email: EmailStr
    phone: Optional[str] = None
    profile_photo_url: Optional[str] = None


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)
    school_id: int
    role_id: int


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    profile_photo_url: Optional[str] = None
    role_id: Optional[int] = None


class UserInDB(UserBase):
    id: int
    school_id: int
    role_id: int
    is_email_verified: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True


class UserWithRole(UserInDB):
    role: RoleInDB
    
    class Config:
        orm_mode = True


# Student schemas
class StudentBase(BaseModel):
    admission_number: str
    date_of_birth: datetime
    gender: Optional[str] = None
    class_id: Optional[int] = None
    department_id: Optional[int] = None
    session_id: Optional[int] = None
    photo_url: Optional[str] = None


class StudentCreate(StudentBase):
    user_id: int
    school_id: int


class StudentUpdate(BaseModel):
    admission_number: Optional[str] = None
    date_of_birth: Optional[datetime] = None
    gender: Optional[str] = None
    class_id: Optional[int] = None
    department_id: Optional[int] = None
    session_id: Optional[int] = None
    photo_url: Optional[str] = None


class StudentInDB(StudentBase):
    id: int
    user_id: int
    school_id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True


class StudentWithUser(StudentInDB):
    user: UserInDB
    
    class Config:
        orm_mode = True


# Parent-Student schemas
class ParentStudentCreate(BaseModel):
    parent_user_id: int
    student_id: int


class ParentStudentInDB(ParentStudentCreate):
    class Config:
        orm_mode = True


# Teacher-Subject-Class schemas
class TeacherSubjectClassCreate(BaseModel):
    teacher_user_id: int
    subject_id: int
    class_id: int


class TeacherSubjectClassInDB(TeacherSubjectClassCreate):
    class Config:
        orm_mode = True


# Authentication schemas
class Token(BaseModel):
    access_token: str
    token_type: str
    user_id: int
    role: str


class TokenData(BaseModel):
    user_id: Optional[int] = None
    role: Optional[str] = None
    school_id: Optional[int] = None
    exp: Optional[datetime] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class PasswordChange(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=8)
