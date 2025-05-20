from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, validator, condecimal


# Academic Session schemas
class AcademicSessionBase(BaseModel):
    name: str
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    
    @validator('end_date')
    def end_date_after_start_date(cls, v, values):
        if 'start_date' in values and v and values['start_date'] and v < values['start_date']:
            raise ValueError('end_date must be after start_date')
        return v


class AcademicSessionCreate(AcademicSessionBase):
    school_id: int


class AcademicSessionUpdate(BaseModel):
    name: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class AcademicSessionInDB(AcademicSessionBase):
    id: int
    school_id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True


# Term schemas
class TermBase(BaseModel):
    name: str
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    
    @validator('end_date')
    def end_date_after_start_date(cls, v, values):
        if 'start_date' in values and v and values['start_date'] and v < values['start_date']:
            raise ValueError('end_date must be after start_date')
        return v


class TermCreate(TermBase):
    session_id: int


class TermUpdate(BaseModel):
    name: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class TermInDB(TermBase):
    id: int
    session_id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True


# Assessment schemas
class AssessmentBase(BaseModel):
    name: str
    max_score: condecimal(max_digits=5, decimal_places=2, ge=0)


class AssessmentCreate(AssessmentBase):
    school_id: int
    term_id: int


class AssessmentUpdate(BaseModel):
    name: Optional[str] = None
    max_score: Optional[condecimal(max_digits=5, decimal_places=2, ge=0)] = None


class AssessmentInDB(AssessmentBase):
    id: int
    school_id: int
    term_id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True


# Student Assessment Score schemas
class StudentAssessmentScoreBase(BaseModel):
    score: condecimal(max_digits=5, decimal_places=2, ge=0)
    
    @validator('score')
    def validate_score(cls, v, values, **kwargs):
        # Custom validation logic if needed
        return v


class StudentAssessmentScoreCreate(StudentAssessmentScoreBase):
    student_id: int
    assessment_id: int
    subject_id: int


class StudentAssessmentScoreUpdate(BaseModel):
    score: condecimal(max_digits=5, decimal_places=2, ge=0)


class StudentAssessmentScoreInDB(StudentAssessmentScoreBase):
    id: int
    student_id: int
    assessment_id: int
    subject_id: int
    created_at: datetime
    
    class Config:
        orm_mode = True


# Report Card schema
class SubjectScore(BaseModel):
    subject_id: int
    subject_name: str
    scores: List[dict]
    total: float
    average: float
    grade: str


class ReportCard(BaseModel):
    student_id: int
    student_name: str
    class_id: int
    class_name: str
    term_id: int
    term_name: str
    session_id: int
    session_name: str
    subjects: List[SubjectScore]
    overall_average: float
    overall_grade: str
    position: Optional[int] = None
    teacher_comment: Optional[str] = None
    principal_comment: Optional[str] = None
