from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Numeric, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

# School model
class School(Base):
    __tablename__ = "schools"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    abbreviation = Column(String(20), unique=True, nullable=False)
    address = Column(Text)
    phone = Column(String(50))
    email = Column(String(100))
    logo_url = Column(Text)
    subscription_plan = Column(String(50), default="free")
    join_code = Column(String(5), unique=True)
    code_expires_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    users = relationship("User", back_populates="school")
    departments = relationship("Department", back_populates="school")
    classes = relationship("Class", back_populates="school")
    subjects = relationship("Subject", back_populates="school")
    sessions = relationship("AcademicSession", back_populates="school")
    students = relationship("Student", back_populates="school")
    locations = relationship("AuthenticLocation", back_populates="school")
    fee_types = relationship("FeeType", back_populates="school")
    assessments = relationship("Assessment", back_populates="school")

# Department model
class Department(Base):
    __tablename__ = "departments"
    
    id = Column(Integer, primary_key=True, index=True)
    school_id = Column(Integer, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    school = relationship("School", back_populates="departments")
    classes = relationship("Class", back_populates="department")
    subjects = relationship("Subject", back_populates="department")
    students = relationship("Student", back_populates="department")

# Class model
class Class(Base):
    __tablename__ = "classes"
    
    id = Column(Integer, primary_key=True, index=True)
    school_id = Column(Integer, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    department_id = Column(Integer, ForeignKey("departments.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    school = relationship("School", back_populates="classes")
    department = relationship("Department", back_populates="classes")
    students = relationship("Student", back_populates="class_")
    attendance_records = relationship("AttendanceRecord", back_populates="class_")
    teacher_subjects = relationship("TeacherSubjectClass", backref="class_")

# Subject model
class Subject(Base):
    __tablename__ = "subjects"
    
    id = Column(Integer, primary_key=True, index=True)
    school_id = Column(Integer, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    department_id = Column(Integer, ForeignKey("departments.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    school = relationship("School", back_populates="subjects")
    department = relationship("Department", back_populates="subjects")
    teacher_classes = relationship("TeacherSubjectClass", backref="subject")
    assessment_scores = relationship("StudentAssessmentScore", back_populates="subject")

# Authentic Location model for GPS verification
class AuthenticLocation(Base):
    __tablename__ = "authentic_locations"
    
    id = Column(Integer, primary_key=True, index=True)
    school_id = Column(Integer, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    latitude = Column(Numeric(9, 6), nullable=False)
    longitude = Column(Numeric(9, 6), nullable=False)
    radius_meters = Column(Integer, default=100, nullable=False)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    school = relationship("School", back_populates="locations")
