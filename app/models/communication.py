from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

# Message model
class Message(Base):
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, index=True)
    sender_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    receiver_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    attachment_url = Column(Text)
    is_group_message = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    read_at = Column(DateTime(timezone=True))
    
    # Relationships
    sender = relationship("User", foreign_keys=[sender_user_id], back_populates="sent_messages")
    receiver = relationship("User", foreign_keys=[receiver_user_id], back_populates="received_messages")

# Behavior Report model
class BehaviorReport(Base):
    __tablename__ = "behavior_reports"
    
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    reported_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    behavior_type = Column(String(100), nullable=False)
    description = Column(Text)
    action_taken = Column(Text)
    report_date = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    student = relationship("Student", back_populates="behavior_reports")
    reported_by = relationship("User", foreign_keys=[reported_by_user_id], back_populates="behavior_reports")

# Audit Log model
class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    action = Column(String(255), nullable=False)
    entity_type = Column(String(100))
    entity_id = Column(Integer)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    ip_address = Column(String(45))
    
    # Relationships
    user = relationship("User", back_populates="audit_logs")
