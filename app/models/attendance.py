from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Numeric, Boolean, CheckConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

# Attendance Record model
class AttendanceRecord(Base):
    __tablename__ = "attendance_records"
    
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False)
    date = Column(DateTime, nullable=False)
    status = Column(String(20), nullable=False)
    marked_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    latitude = Column(Numeric(9, 6))
    longitude = Column(Numeric(9, 6))
    flagged = Column(Boolean, default=False)
    flagged_reason = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Check constraint to ensure status is valid
    __table_args__ = (
        CheckConstraint("status IN ('Present', 'Absent', 'Late', 'Excused')", name="check_attendance_status"),
    )
    
    # Relationships
    student = relationship("Student", back_populates="attendance_records")
    class_ = relationship("Class", back_populates="attendance_records")
    marked_by = relationship("User", foreign_keys=[marked_by_user_id])
