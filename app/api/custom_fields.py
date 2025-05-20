from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Path, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_

from app.database import get_db
from app.models.users import Student
from app.models.custom_fields import StudentCustomField
from app.middleware.authentication import get_current_user
from app.schemas.custom_fields import (
    StudentCustomFieldCreate,
    StudentCustomFieldUpdate,
    StudentCustomFieldResponse
)

router = APIRouter()

@router.post("/students/{student_id}/custom-fields", response_model=StudentCustomFieldResponse)
async def create_student_custom_field(
    student_id: int = Path(..., gt=0),
    field_data: StudentCustomFieldCreate = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Create a new custom field for a student.
    """
    # Check if student exists
    result = await db.execute(select(Student).where(Student.id == student_id))
    student = result.scalars().first()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found"
        )
    
    # Check if field key already exists for this student
    result = await db.execute(
        select(StudentCustomField).where(
            and_(
                StudentCustomField.student_id == student_id,
                StudentCustomField.field_key == field_data.field_key
            )
        )
    )
    existing_field = result.scalars().first()
    
    if existing_field:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Field with key '{field_data.field_key}' already exists for this student"
        )
    
    # Create new custom field
    new_field = StudentCustomField(
        student_id=student_id,
        field_key=field_data.field_key,
        field_value=field_data.field_value
    )
    
    db.add(new_field)
    await db.commit()
    await db.refresh(new_field)
    
    return new_field

@router.get("/students/{student_id}/custom-fields", response_model=List[StudentCustomFieldResponse])
async def get_student_custom_fields(
    student_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Get all custom fields for a student.
    """
    # Check if student exists
    result = await db.execute(select(Student).where(Student.id == student_id))
    student = result.scalars().first()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found"
        )
    
    # Get all custom fields for the student
    result = await db.execute(
        select(StudentCustomField).where(StudentCustomField.student_id == student_id)
    )
    
    fields = result.scalars().all()
    
    return fields

@router.put("/students/{student_id}/custom-fields/{field_key}", response_model=StudentCustomFieldResponse)
async def update_student_custom_field(
    student_id: int = Path(..., gt=0),
    field_key: str = Path(...),
    field_data: StudentCustomFieldUpdate = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Update a custom field for a student.
    """
    # Check if student exists
    result = await db.execute(select(Student).where(Student.id == student_id))
    student = result.scalars().first()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found"
        )
    
    # Get the field to update
    result = await db.execute(
        select(StudentCustomField).where(
            and_(
                StudentCustomField.student_id == student_id,
                StudentCustomField.field_key == field_key
            )
        )
    )
    field = result.scalars().first()
    
    if not field:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Field with key '{field_key}' not found for this student"
        )
    
    # Update the field value
    field.field_value = field_data.field_value
    
    await db.commit()
    await db.refresh(field)
    
    return field

@router.delete("/students/{student_id}/custom-fields/{field_key}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_student_custom_field(
    student_id: int = Path(..., gt=0),
    field_key: str = Path(...),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Delete a custom field for a student.
    """
    # Check if student exists
    result = await db.execute(select(Student).where(Student.id == student_id))
    student = result.scalars().first()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found"
        )
    
    # Get the field to delete
    result = await db.execute(
        select(StudentCustomField).where(
            and_(
                StudentCustomField.student_id == student_id,
                StudentCustomField.field_key == field_key
            )
        )
    )
    field = result.scalars().first()
    
    if not field:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Field with key '{field_key}' not found for this student"
        )
    
    # Delete the field
    await db.delete(field)
    await db.commit()