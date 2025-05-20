from datetime import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, Text, Boolean, DateTime, Table
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

# Role-Permission association table
class RolePermission(Base):
    __tablename__ = "role_permissions"
    
    role_id = Column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
    permission_id = Column(Integer, ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True)

# Permissions
class Permission(Base):
    __tablename__ = "permissions"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text)
    
    # Relationships
    roles = relationship("Role", secondary="role_permissions", back_populates="permissions")

# Roles
class Role(Base):
    __tablename__ = "roles"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)
    description = Column(Text)
    
    # Relationships
    permissions = relationship("Permission", secondary="role_permissions", back_populates="roles")
    users = relationship("User", back_populates="role")

# Users
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    school_id = Column(Integer, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    hashed_password = Column(Text, nullable=False)
    profile_photo_url = Column(Text)
    phone = Column(String(50))
    is_email_verified = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    school = relationship("School", back_populates="users")
    role = relationship("Role", back_populates="users")
    student = relationship("Student", back_populates="user", uselist=False)
    sent_messages = relationship("Message", foreign_keys="Message.sender_user_id", back_populates="sender")
    received_messages = relationship("Message", foreign_keys="Message.receiver_user_id", back_populates="receiver")
    audit_logs = relationship("AuditLog", back_populates="user")
    behavior_reports = relationship("BehaviorReport", foreign_keys="BehaviorReport.reported_by_user_id", back_populates="reported_by")

# Parent-Student association
class ParentStudent(Base):
    __tablename__ = "parents_students"
    
    parent_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), primary_key=True)

# Teacher-Subject-Class association
class TeacherSubjectClass(Base):
    __tablename__ = "teachers_subjects_classes"
    
    teacher_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), primary_key=True)
    class_id = Column(Integer, ForeignKey("classes.id", ondelete="CASCADE"), primary_key=True)

# Student model
class Student(Base):
    __tablename__ = "students"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    school_id = Column(Integer, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    admission_number = Column(String(100), unique=True, nullable=False)
    date_of_birth = Column(DateTime, nullable=False)
    gender = Column(String(20))
    class_id = Column(Integer, ForeignKey("classes.id"))
    department_id = Column(Integer, ForeignKey("departments.id"))
    session_id = Column(Integer, ForeignKey("academic_sessions.id"))
    photo_url = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="student")
    school = relationship("School", back_populates="students")
    class_ = relationship("Class", back_populates="students")
    department = relationship("Department", back_populates="students")
    session = relationship("AcademicSession", back_populates="students")
    parents = relationship("User", secondary="parents_students", primaryjoin="Student.id==ParentStudent.student_id", 
                           secondaryjoin="ParentStudent.parent_user_id==User.id")
    attendance_records = relationship("AttendanceRecord", back_populates="student")
    assessment_scores = relationship("StudentAssessmentScore", back_populates="student")
    fees = relationship("StudentFee", back_populates="student")
    behavior_reports = relationship("BehaviorReport", back_populates="student")
    custom_fields = relationship("StudentCustomField", back_populates="student")
