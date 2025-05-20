from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Numeric, CheckConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

# Academic Session model
class AcademicSession(Base):
    __tablename__ = "academic_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    school_id = Column(Integer, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(50), nullable=False)
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    school = relationship("School", back_populates="sessions")
    terms = relationship("Term", back_populates="session")
    students = relationship("Student", back_populates="session")

# Term model
class Term(Base):
    __tablename__ = "terms"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("academic_sessions.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(50), nullable=False)
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    session = relationship("AcademicSession", back_populates="terms")
    assessments = relationship("Assessment", back_populates="term")

# Assessment model
class Assessment(Base):
    __tablename__ = "assessments"
    
    id = Column(Integer, primary_key=True, index=True)
    school_id = Column(Integer, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    term_id = Column(Integer, ForeignKey("terms.id", ondelete="CASCADE"), nullable=False)
    max_score = Column(Numeric(5, 2), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    school = relationship("School", back_populates="assessments")
    term = relationship("Term", back_populates="assessments")
    scores = relationship("StudentAssessmentScore", back_populates="assessment")

# Student Assessment Score model
class StudentAssessmentScore(Base):
    __tablename__ = "student_assessment_scores"
    
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    assessment_id = Column(Integer, ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    score = Column(Numeric(5, 2), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Check constraint to ensure score is not negative
    __table_args__ = (
        CheckConstraint("score >= 0", name="check_score_positive"),
    )
    
    # Relationships
    student = relationship("Student", back_populates="assessment_scores")
    assessment = relationship("Assessment", back_populates="scores")
    subject = relationship("Subject", back_populates="assessment_scores")
