from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, Field, validator, condecimal
from enum import Enum


class FeeStatusEnum(str, Enum):
    pending = "pending"
    partial = "partial"
    paid = "paid"
    overdue = "overdue"


class PaymentMethodEnum(str, Enum):
    paystack = "paystack"
    manual = "manual"


# Fee Type schemas
class FeeTypeBase(BaseModel):
    name: str
    description: Optional[str] = None
    amount: condecimal(max_digits=12, decimal_places=2, gt=0)


class FeeTypeCreate(FeeTypeBase):
    school_id: int


class FeeTypeUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    amount: Optional[condecimal(max_digits=12, decimal_places=2, gt=0)] = None


class FeeTypeInDB(FeeTypeBase):
    id: int
    school_id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True


# Student Fee schemas
class StudentFeeBase(BaseModel):
    amount_due: condecimal(max_digits=12, decimal_places=2, gt=0)
    amount_paid: condecimal(max_digits=12, decimal_places=2, ge=0) = 0
    status: FeeStatusEnum = FeeStatusEnum.pending
    due_date: Optional[date] = None


class StudentFeeCreate(StudentFeeBase):
    student_id: int
    fee_type_id: int


class StudentFeeUpdate(BaseModel):
    amount_due: Optional[condecimal(max_digits=12, decimal_places=2, gt=0)] = None
    amount_paid: Optional[condecimal(max_digits=12, decimal_places=2, ge=0)] = None
    status: Optional[FeeStatusEnum] = None
    due_date: Optional[date] = None


class StudentFeeInDB(StudentFeeBase):
    id: int
    student_id: int
    fee_type_id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True


# Payment schemas
class PaymentBase(BaseModel):
    amount: condecimal(max_digits=12, decimal_places=2, gt=0)
    payment_method: PaymentMethodEnum
    payment_reference: Optional[str] = None


class PaymentCreate(PaymentBase):
    student_fee_id: int


class PaymentInDB(PaymentBase):
    id: int
    student_fee_id: int
    payment_date: datetime
    created_at: datetime
    
    class Config:
        orm_mode = True


# PayStack payment initialization
class PaystackPaymentInit(BaseModel):
    student_fee_id: int
    amount: condecimal(max_digits=12, decimal_places=2, gt=0)
    email: str
    callback_url: Optional[str] = None


class PaystackPaymentResponse(BaseModel):
    authorization_url: str
    access_code: str
    reference: str


# Payment verification
class PaymentVerification(BaseModel):
    reference: str


class PaymentVerificationResponse(BaseModel):
    is_successful: bool
    amount: Optional[float] = None
    transaction_date: Optional[datetime] = None
    message: str


# Fee Summary
class FeeSummary(BaseModel):
    total_due: float
    total_paid: float
    total_balance: float
    payment_status: FeeStatusEnum
