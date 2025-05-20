from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Numeric, CheckConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

# Fee Type model
class FeeType(Base):
    __tablename__ = "fee_types"
    
    id = Column(Integer, primary_key=True, index=True)
    school_id = Column(Integer, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    amount = Column(Numeric(12, 2), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    school = relationship("School", back_populates="fee_types")
    student_fees = relationship("StudentFee", back_populates="fee_type")

# Student Fee model
class StudentFee(Base):
    __tablename__ = "student_fees"
    
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    fee_type_id = Column(Integer, ForeignKey("fee_types.id"), nullable=False)
    amount_due = Column(Numeric(12, 2), nullable=False)
    amount_paid = Column(Numeric(12, 2), default=0)
    status = Column(String(20), default="pending", nullable=False)
    due_date = Column(DateTime)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Check constraint to ensure status is valid
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'partial', 'paid', 'overdue')", name="check_fee_status"),
    )
    
    # Relationships
    student = relationship("Student", back_populates="fees")
    fee_type = relationship("FeeType", back_populates="student_fees")
    payments = relationship("Payment", back_populates="student_fee")

# Payment model
class Payment(Base):
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True, index=True)
    student_fee_id = Column(Integer, ForeignKey("student_fees.id", ondelete="CASCADE"), nullable=False)
    payment_date = Column(DateTime, nullable=False, server_default=func.now())
    amount = Column(Numeric(12, 2), nullable=False)
    payment_reference = Column(String(255))
    payment_method = Column(String(50))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    student_fee = relationship("StudentFee", back_populates="payments")
