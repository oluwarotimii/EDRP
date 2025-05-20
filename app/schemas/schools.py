from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field, validator, HttpUrl
from enum import Enum


class SubscriptionPlanEnum(str, Enum):
    free = "free"
    premium = "premium"
    enterprise = "enterprise"


# School schemas
class SchoolBase(BaseModel):
    name: str
    abbreviation: str
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    logo_url: Optional[str] = None
    subscription_plan: SubscriptionPlanEnum = SubscriptionPlanEnum.free


class SchoolCreate(SchoolBase):
    pass


class SchoolUpdate(BaseModel):
    name: Optional[str] = None
    abbreviation: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    logo_url: Optional[str] = None
    subscription_plan: Optional[SubscriptionPlanEnum] = None


class SchoolInDB(SchoolBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True


# Department schemas
class DepartmentBase(BaseModel):
    name: str
    description: Optional[str] = None


class DepartmentCreate(DepartmentBase):
    school_id: int


class DepartmentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class DepartmentInDB(DepartmentBase):
    id: int
    school_id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True


# Class schemas
class ClassBase(BaseModel):
    name: str
    department_id: Optional[int] = None


class ClassCreate(ClassBase):
    school_id: int


class ClassUpdate(BaseModel):
    name: Optional[str] = None
    department_id: Optional[int] = None


class ClassInDB(ClassBase):
    id: int
    school_id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True


# Subject schemas
class SubjectBase(BaseModel):
    name: str
    department_id: Optional[int] = None


class SubjectCreate(SubjectBase):
    school_id: int


class SubjectUpdate(BaseModel):
    name: Optional[str] = None
    department_id: Optional[int] = None


class SubjectInDB(SubjectBase):
    id: int
    school_id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True


# Authentic Location schemas
class AuthenticLocationBase(BaseModel):
    name: str
    latitude: float
    longitude: float
    radius_meters: int = 100
    active: bool = True


class AuthenticLocationCreate(AuthenticLocationBase):
    school_id: int


class AuthenticLocationUpdate(BaseModel):
    name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    radius_meters: Optional[int] = None
    active: Optional[bool] = None


class AuthenticLocationInDB(AuthenticLocationBase):
    id: int
    school_id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True
