from typing import List, Optional
from datetime import date, datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import or_, and_, func, desc, asc

from app.database import get_db
from app.schemas.attendance import (
    AttendanceRecordCreate, AttendanceRecordUpdate, AttendanceRecordInDB,
    BulkAttendanceCreate, AttendanceStats, GPSVerificationRequest, GPSVerificationResponse
)
from app.models.users import User, Student
from app.models.schools import School, Class, AuthenticLocation
from app.models.attendance import AttendanceRecord
from app.middleware.authentication import get_current_user, RoleChecker
from app.services.gps import verify_location

router = APIRouter()

# Role-based access control
allow_attendance_management = RoleChecker(["super_admin", "admin_staff", "class_teacher", "subject_teacher"])

@router.post("/attendance/verify-location", response_model=GPSVerificationResponse)
async def verify_attendance_location(
    location_data: GPSVerificationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Verify if a location is within the authentic zones of a school.
    """
    # Check if user has access to this school
    if current_user.role.name != "super_admin" and current_user.school_id != location_data.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to verify locations for this school"
        )
    
    # Get authentic locations for the school
    result = await db.execute(
        select(AuthenticLocation).where(
            and_(
                AuthenticLocation.school_id == location_data.school_id,
                AuthenticLocation.active == True
            )
        )
    )
    locations = result.scalars().all()
    
    if not locations:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No authentic locations defined for this school"
        )
    
    # Verify the location against all authentic locations
    is_valid = False
    closest_distance = float('inf')
    closest_location = None
    
    for location in locations:
        distance = verify_location(
            location_data.latitude, 
            location_data.longitude,
            float(location.latitude), 
            float(location.longitude),
            location.radius_meters
        )
        
        if distance <= location.radius_meters:
            is_valid = True
            if distance < closest_distance:
                closest_distance = distance
                closest_location = location
    
    if is_valid:
        return {
            "is_valid": True,
            "distance": closest_distance,
            "location_name": closest_location.name,
            "message": f"Location verified as authentic (within {int(closest_distance)}m of {closest_location.name})"
        }
    else:
        return {
            "is_valid": False,
            "distance": min(verify_location(
                location_data.latitude, 
                location_data.longitude,
                float(loc.latitude), 
                float(loc.longitude)
            ) for loc in locations),
            "message": "Location is outside of all authentic zones for this school"
        }

@router.post("/attendance", response_model=AttendanceRecordInDB, status_code=status.HTTP_201_CREATED)
async def create_attendance_record(
    attendance_data: AttendanceRecordCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new attendance record for a student.
    """
    # Check if user has permission to manage attendance
    if current_user.role.name not in ["super_admin", "admin_staff", "class_teacher", "subject_teacher"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to create attendance records"
        )
    
    # Verify student exists
    student_result = await db.execute(select(Student).where(Student.id == attendance_data.student_id))
    student = student_result.scalars().first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found"
        )
    
    # Check if user has access to student's school
    if current_user.role.name != "super_admin" and current_user.school_id != student.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to create attendance for students from another school"
        )
    
    # Verify class exists
    class_result = await db.execute(select(Class).where(Class.id == attendance_data.class_id))
    class_ = class_result.scalars().first()
    if not class_:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Class not found"
        )
    
    # Check if class belongs to student's school
    if class_.school_id != student.school_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Class and student must be from the same school"
        )
    
    # Check if a record already exists for this student on this day
    existing_result = await db.execute(
        select(AttendanceRecord).where(
            and_(
                AttendanceRecord.student_id == attendance_data.student_id,
                AttendanceRecord.date == attendance_data.date
            )
        )
    )
    existing_record = existing_result.scalars().first()
    if existing_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Attendance record already exists for this student on this date"
        )
    
    # Verify location if GPS coordinates are provided
    flagged = False
    flagged_reason = None
    
    if attendance_data.latitude is not None and attendance_data.longitude is not None:
        # Get authentic locations for the school
        locations_result = await db.execute(
            select(AuthenticLocation).where(
                and_(
                    AuthenticLocation.school_id == student.school_id,
                    AuthenticLocation.active == True
                )
            )
        )
        locations = locations_result.scalars().all()
        
        if locations:
            is_valid = False
            for location in locations:
                distance = verify_location(
                    attendance_data.latitude, 
                    attendance_data.longitude,
                    float(location.latitude), 
                    float(location.longitude),
                    location.radius_meters
                )
                
                if distance <= location.radius_meters:
                    is_valid = True
                    break
            
            if not is_valid:
                flagged = True
                flagged_reason = "Location is outside of all authentic zones for this school"
    
    # Create attendance record
    attendance_record = AttendanceRecord(
        student_id=attendance_data.student_id,
        class_id=attendance_data.class_id,
        date=attendance_data.date,
        status=attendance_data.status,
        marked_by_user_id=attendance_data.marked_by_user_id,
        latitude=attendance_data.latitude,
        longitude=attendance_data.longitude,
        flagged=flagged,
        flagged_reason=flagged_reason
    )
    
    db.add(attendance_record)
    await db.commit()
    await db.refresh(attendance_record)
    
    return attendance_record

@router.post("/attendance/bulk", response_model=List[AttendanceRecordInDB], status_code=status.HTTP_201_CREATED)
async def create_bulk_attendance(
    bulk_data: BulkAttendanceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create attendance records for multiple students at once.
    """
    # Check if user has permission to manage attendance
    if current_user.role.name not in ["super_admin", "admin_staff", "class_teacher", "subject_teacher"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to create attendance records"
        )
    
    # Verify class exists
    class_result = await db.execute(select(Class).where(Class.id == bulk_data.class_id))
    class_ = class_result.scalars().first()
    if not class_:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Class not found"
        )
    
    # Check if user has access to this class's school
    if current_user.role.name != "super_admin" and current_user.school_id != class_.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to create attendance for students from another school"
        )
    
    # Verify all students exist and belong to the same school
    student_ids = [record.student_id for record in bulk_data.records]
    students_result = await db.execute(select(Student).where(Student.id.in_(student_ids)))
    students = {student.id: student for student in students_result.scalars().all()}
    
    if len(students) != len(student_ids):
        missing_ids = set(student_ids) - set(students.keys())
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Some students not found: {missing_ids}"
        )
    
    for student in students.values():
        if student.school_id != class_.school_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Student {student.id} belongs to a different school than the class"
            )
    
    # Verify location if GPS coordinates are provided
    flagged = False
    flagged_reason = None
    
    if bulk_data.latitude is not None and bulk_data.longitude is not None:
        # Get authentic locations for the school
        locations_result = await db.execute(
            select(AuthenticLocation).where(
                and_(
                    AuthenticLocation.school_id == class_.school_id,
                    AuthenticLocation.active == True
                )
            )
        )
        locations = locations_result.scalars().all()
        
        if locations:
            is_valid = False
            for location in locations:
                distance = verify_location(
                    bulk_data.latitude, 
                    bulk_data.longitude,
                    float(location.latitude), 
                    float(location.longitude),
                    location.radius_meters
                )
                
                if distance <= location.radius_meters:
                    is_valid = True
                    break
            
            if not is_valid:
                flagged = True
                flagged_reason = "Location is outside of all authentic zones for this school"
    
    # Check for existing records and create new ones
    attendance_records = []
    
    for record_data in bulk_data.records:
        # Check if a record already exists for this student on this day
        existing_result = await db.execute(
            select(AttendanceRecord).where(
                and_(
                    AttendanceRecord.student_id == record_data.student_id,
                    AttendanceRecord.date == bulk_data.date
                )
            )
        )
        existing_record = existing_result.scalars().first()
        
        if existing_record:
            # Update existing record
            existing_record.status = record_data.status
            existing_record.marked_by_user_id = bulk_data.marked_by_user_id
            existing_record.latitude = bulk_data.latitude
            existing_record.longitude = bulk_data.longitude
            existing_record.flagged = flagged
            existing_record.flagged_reason = flagged_reason
            attendance_records.append(existing_record)
        else:
            # Create new record
            attendance_record = AttendanceRecord(
                student_id=record_data.student_id,
                class_id=bulk_data.class_id,
                date=bulk_data.date,
                status=record_data.status,
                marked_by_user_id=bulk_data.marked_by_user_id,
                latitude=bulk_data.latitude,
                longitude=bulk_data.longitude,
                flagged=flagged,
                flagged_reason=flagged_reason
            )
            db.add(attendance_record)
            attendance_records.append(attendance_record)
    
    await db.commit()
    
    # Refresh all records to get updated values
    for record in attendance_records:
        await db.refresh(record)
    
    return attendance_records

@router.get("/attendance", response_model=List[AttendanceRecordInDB])
async def get_attendance_records(
    student_id: Optional[int] = Query(None),
    class_id: Optional[int] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    status: Optional[str] = Query(None),
    flagged: Optional[bool] = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get attendance records with optional filtering.
    """
    # Build base query
    query = select(AttendanceRecord)
    
    # Apply filters
    if student_id:
        query = query.where(AttendanceRecord.student_id == student_id)
        
        # Check permissions: only allow access to students from user's school
        if current_user.role.name != "super_admin":
            student_result = await db.execute(select(Student).where(Student.id == student_id))
            student = student_result.scalars().first()
            if student and student.school_id != current_user.school_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to view attendance for students from another school"
                )
    
    if class_id:
        query = query.where(AttendanceRecord.class_id == class_id)
        
        # Check permissions: only allow access to classes from user's school
        if current_user.role.name != "super_admin":
            class_result = await db.execute(select(Class).where(Class.id == class_id))
            class_ = class_result.scalars().first()
            if class_ and class_.school_id != current_user.school_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to view attendance for classes from another school"
                )
    
    if start_date:
        query = query.where(AttendanceRecord.date >= start_date)
    
    if end_date:
        query = query.where(AttendanceRecord.date <= end_date)
    
    if status:
        query = query.where(AttendanceRecord.status == status)
    
    if flagged is not None:
        query = query.where(AttendanceRecord.flagged == flagged)
    
    # If not a super_admin, only show records from user's school
    if current_user.role.name != "super_admin":
        # Join with Student and filter by school_id
        query = query.join(Student).where(Student.school_id == current_user.school_id)
    
    # Apply pagination
    query = query.order_by(desc(AttendanceRecord.date), AttendanceRecord.student_id)
    query = query.offset(skip).limit(limit)
    
    # Execute query
    result = await db.execute(query)
    records = result.scalars().all()
    
    return records

@router.get("/attendance/{record_id}", response_model=AttendanceRecordInDB)
async def get_attendance_record(
    record_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific attendance record by ID.
    """
    result = await db.execute(select(AttendanceRecord).where(AttendanceRecord.id == record_id))
    record = result.scalars().first()
    
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attendance record not found"
        )
    
    # Check if user has access to this student's school
    if current_user.role.name != "super_admin":
        student_result = await db.execute(select(Student).where(Student.id == record.student_id))
        student = student_result.scalars().first()
        if student and student.school_id != current_user.school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view attendance for students from another school"
            )
    
    return record

@router.put("/attendance/{record_id}", response_model=AttendanceRecordInDB)
async def update_attendance_record(
    attendance_data: AttendanceRecordUpdate,
    record_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update an attendance record.
    """
    # Check if user has permission to manage attendance
    if current_user.role.name not in ["super_admin", "admin_staff", "class_teacher"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update attendance records"
        )
    
    # Get the record
    result = await db.execute(select(AttendanceRecord).where(AttendanceRecord.id == record_id))
    record = result.scalars().first()
    
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attendance record not found"
        )
    
    # Check if user has access to this student's school
    if current_user.role.name != "super_admin":
        student_result = await db.execute(select(Student).where(Student.id == record.student_id))
        student = student_result.scalars().first()
        if student and student.school_id != current_user.school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update attendance for students from another school"
            )
    
    # Update record
    update_data = attendance_data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(record, key, value)
    
    await db.commit()
    await db.refresh(record)
    
    return record

@router.get("/attendance/statistics/student/{student_id}", response_model=AttendanceStats)
async def get_student_attendance_statistics(
    student_id: int = Path(..., gt=0),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get attendance statistics for a specific student.
    """
    # Verify student exists
    student_result = await db.execute(select(Student).where(Student.id == student_id))
    student = student_result.scalars().first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found"
        )
    
    # Check if user has access to this student's school
    if current_user.role.name != "super_admin" and current_user.school_id != student.school_id:
        # Check if the current user is a parent of this student
        if current_user.role.name == "parent":
            parent_student_result = await db.execute(
                select(User).join(
                    "student_parents",
                    User.id == student.id
                ).where(User.id == current_user.id)
            )
            is_parent = parent_student_result.scalars().first() is not None
            if not is_parent:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to view attendance for this student"
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view attendance for students from another school"
            )
    
    # Set default date range if not provided
    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=30)  # Default to last 30 days
    
    # Query attendance records
    query = select(AttendanceRecord).where(
        and_(
            AttendanceRecord.student_id == student_id,
            AttendanceRecord.date >= start_date,
            AttendanceRecord.date <= end_date
        )
    )
    
    result = await db.execute(query)
    records = result.scalars().all()
    
    # Calculate statistics
    total_days = len(records)
    present_days = sum(1 for r in records if r.status == "Present")
    absent_days = sum(1 for r in records if r.status == "Absent")
    late_days = sum(1 for r in records if r.status == "Late")
    excused_days = sum(1 for r in records if r.status == "Excused")
    
    attendance_percentage = (present_days + excused_days) / total_days * 100 if total_days > 0 else 0
    
    return {
        "total_days": total_days,
        "present_days": present_days,
        "absent_days": absent_days,
        "late_days": late_days,
        "excused_days": excused_days,
        "attendance_percentage": attendance_percentage
    }

@router.get("/attendance/statistics/class/{class_id}", response_model=dict)
async def get_class_attendance_statistics(
    class_id: int = Path(..., gt=0),
    date_param: Optional[date] = Query(None, alias="date"),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get attendance statistics for a class.
    """
    # Verify class exists
    class_result = await db.execute(select(Class).where(Class.id == class_id))
    class_ = class_result.scalars().first()
    if not class_:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Class not found"
        )
    
    # Check if user has access to this class's school
    if current_user.role.name != "super_admin" and current_user.school_id != class_.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view attendance for classes from another school"
        )
    
    # Set up date parameters
    if date_param:
        # If specific date is provided, only get that day
        start_date = date_param
        end_date = date_param
    elif not end_date:
        # Default to today if not specified
        end_date = date.today()
        if not start_date:
            start_date = end_date  # Default to just today
    
    # Get all students in the class
    students_result = await db.execute(select(Student).where(Student.class_id == class_id))
    students = students_result.scalars().all()
    student_ids = [student.id for student in students]
    
    if not student_ids:
        return {
            "class_id": class_id,
            "class_name": class_.name,
            "date_range": {
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat() if end_date else None
            },
            "statistics": {
                "total_students": 0,
                "present": 0,
                "absent": 0,
                "late": 0,
                "excused": 0,
                "not_marked": 0,
                "attendance_rate": 0
            }
        }
    
    # Query attendance records
    query = select(AttendanceRecord).where(
        and_(
            AttendanceRecord.student_id.in_(student_ids),
            AttendanceRecord.date >= start_date if start_date else True,
            AttendanceRecord.date <= end_date if end_date else True
        )
    )
    
    result = await db.execute(query)
    records = result.scalars().all()
    
    # Organize records by date
    records_by_date = {}
    for record in records:
        record_date = record.date.isoformat()
        if record_date not in records_by_date:
            records_by_date[record_date] = {}
        records_by_date[record_date][record.student_id] = record.status
    
    # Calculate overall statistics
    total_students = len(student_ids)
    total_possible_records = total_students * len(records_by_date) if records_by_date else 0
    
    present_count = sum(1 for date_records in records_by_date.values() 
                      for status in date_records.values() if status == "Present")
    absent_count = sum(1 for date_records in records_by_date.values() 
                     for status in date_records.values() if status == "Absent")
    late_count = sum(1 for date_records in records_by_date.values() 
                    for status in date_records.values() if status == "Late")
    excused_count = sum(1 for date_records in records_by_date.values() 
                      for status in date_records.values() if status == "Excused")
    
    not_marked = total_possible_records - (present_count + absent_count + late_count + excused_count)
    attendance_rate = (present_count + excused_count) / total_possible_records * 100 if total_possible_records > 0 else 0
    
    return {
        "class_id": class_id,
        "class_name": class_.name,
        "date_range": {
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None
        },
        "statistics": {
            "total_students": total_students,
            "present": present_count,
            "absent": absent_count,
            "late": late_count,
            "excused": excused_count,
            "not_marked": not_marked,
            "attendance_rate": attendance_rate
        },
        "daily_data": records_by_date
    }
