from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Boolean, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

# Custom Student Fields model
class StudentCustomField(Base):
    __tablename__ = "student_custom_fields"
    
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    field_key = Column(String(100), nullable=False)
    field_value = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    student = relationship("Student", back_populates="custom_fields")
    
    # Composite unique constraint to prevent duplicate keys for the same student
    __table_args__ = (
        UniqueConstraint('student_id', 'field_key', name='uix_student_field_key'),
    )