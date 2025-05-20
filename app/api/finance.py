from typing import List, Optional
from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import or_, and_, func, desc, asc, case

from app.database import get_db
from app.schemas.finance import (
    FeeTypeCreate, FeeTypeUpdate, FeeTypeInDB,
    StudentFeeCreate, StudentFeeUpdate, StudentFeeInDB,
    PaymentCreate, PaymentInDB, FeeSummary,
    PaystackPaymentInit, PaystackPaymentResponse,
    PaymentVerification, PaymentVerificationResponse
)
from app.models.finance import FeeType, StudentFee, Payment
from app.models.users import User, Student
from app.models.schools import School
from app.middleware.authentication import get_current_user, validate_admin_access, RoleChecker
from app.services.payments import initialize_payment, verify_payment

router = APIRouter()

# Role-based access control
allow_fee_management = RoleChecker(["super_admin", "admin_staff"])

# Fee Type endpoints
@router.post("/fee-types", response_model=FeeTypeInDB, status_code=status.HTTP_201_CREATED)
async def create_fee_type(
    fee_type_data: FeeTypeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new fee type.
    """
    # Check if user has permission to manage fees
    await validate_admin_access(current_user, db)
    
    # Validate school access
    if current_user.role.name != "super_admin" and current_user.school_id != fee_type_data.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to create fee types for this school"
        )
    
    # Check if fee type with same name exists in this school
    existing_result = await db.execute(
        select(FeeType).where(
            and_(
                FeeType.name == fee_type_data.name,
                FeeType.school_id == fee_type_data.school_id
            )
        )
    )
    existing_fee_type = existing_result.scalars().first()
    if existing_fee_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Fee type with this name already exists for this school"
        )
    
    # Create new fee type
    db_fee_type = FeeType(**fee_type_data.dict())
    db.add(db_fee_type)
    await db.commit()
    await db.refresh(db_fee_type)
    
    return db_fee_type

@router.get("/fee-types", response_model=List[FeeTypeInDB])
async def get_fee_types(
    school_id: Optional[int] = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all fee types, optionally filtered by school.
    """
    # Build query
    query = select(FeeType)
    
    # Filter by school
    if school_id:
        # Check if user has access to this school
        if current_user.role.name != "super_admin" and current_user.school_id != school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view fee types for this school"
            )
        query = query.where(FeeType.school_id == school_id)
    elif current_user.role.name != "super_admin":
        # Regular users can only see fee types from their own school
        query = query.where(FeeType.school_id == current_user.school_id)
    
    # Apply pagination
    query = query.offset(skip).limit(limit)
    
    # Execute query
    result = await db.execute(query)
    fee_types = result.scalars().all()
    
    return fee_types

@router.get("/fee-types/{fee_type_id}", response_model=FeeTypeInDB)
async def get_fee_type(
    fee_type_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific fee type by ID.
    """
    result = await db.execute(select(FeeType).where(FeeType.id == fee_type_id))
    fee_type = result.scalars().first()
    
    if not fee_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fee type not found"
        )
    
    # Check if user has access to this fee type's school
    if current_user.role.name != "super_admin" and current_user.school_id != fee_type.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view fee types from another school"
        )
    
    return fee_type

@router.put("/fee-types/{fee_type_id}", response_model=FeeTypeInDB)
async def update_fee_type(
    fee_type_data: FeeTypeUpdate,
    fee_type_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update a fee type.
    """
    # Check if user has permission to manage fees
    await validate_admin_access(current_user, db)
    
    # Get fee type
    result = await db.execute(select(FeeType).where(FeeType.id == fee_type_id))
    fee_type = result.scalars().first()
    
    if not fee_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fee type not found"
        )
    
    # Check if user has access to this fee type's school
    if current_user.role.name != "super_admin" and current_user.school_id != fee_type.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update fee types from another school"
        )
    
    # Update fee type
    update_data = fee_type_data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(fee_type, key, value)
    
    await db.commit()
    await db.refresh(fee_type)
    
    return fee_type

# Student Fee endpoints
@router.post("/student-fees", response_model=StudentFeeInDB, status_code=status.HTTP_201_CREATED)
async def create_student_fee(
    student_fee_data: StudentFeeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Assign a fee to a student.
    """
    # Check if user has permission to manage student fees
    await validate_admin_access(current_user, db)
    
    # Validate student exists
    student_result = await db.execute(select(Student).where(Student.id == student_fee_data.student_id))
    student = student_result.scalars().first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found"
        )
    
    # Validate fee type exists
    fee_type_result = await db.execute(select(FeeType).where(FeeType.id == student_fee_data.fee_type_id))
    fee_type = fee_type_result.scalars().first()
    if not fee_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fee type not found"
        )
    
    # Check if user has access to student's school
    if current_user.role.name != "super_admin" and current_user.school_id != student.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to assign fees to students from another school"
        )
    
    # Check if fee type belongs to the student's school
    if fee_type.school_id != student.school_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Fee type and student must be from the same school"
        )
    
    # Create student fee
    db_student_fee = StudentFee(**student_fee_data.dict())
    db.add(db_student_fee)
    await db.commit()
    await db.refresh(db_student_fee)
    
    return db_student_fee

@router.post("/student-fees/bulk", response_model=List[StudentFeeInDB], status_code=status.HTTP_201_CREATED)
async def create_bulk_student_fees(
    student_ids: List[int] = Body(..., embed=True),
    fee_type_id: int = Body(..., embed=True),
    amount_due: float = Body(..., embed=True),
    due_date: Optional[date] = Body(None, embed=True),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Assign a fee to multiple students at once.
    """
    # Check if user has permission to manage student fees
    await validate_admin_access(current_user, db)
    
    if not student_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No students provided"
        )
    
    # Validate fee type exists
    fee_type_result = await db.execute(select(FeeType).where(FeeType.id == fee_type_id))
    fee_type = fee_type_result.scalars().first()
    if not fee_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fee type not found"
        )
    
    # Check if user has access to fee type's school
    if current_user.role.name != "super_admin" and current_user.school_id != fee_type.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to assign fees for this school"
        )
    
    # Get all students in one query
    students_result = await db.execute(select(Student).where(Student.id.in_(student_ids)))
    students = {student.id: student for student in students_result.scalars().all()}
    
    # Check if any students are missing
    missing_student_ids = set(student_ids) - set(students.keys())
    if missing_student_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Some students not found: {missing_student_ids}"
        )
    
    # Check if all students belong to the same school as the fee type
    for student in students.values():
        if student.school_id != fee_type.school_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Student {student.id} belongs to a different school than the fee type"
            )
    
    # Create student fees
    student_fees = []
    for student_id in student_ids:
        student_fee = StudentFee(
            student_id=student_id,
            fee_type_id=fee_type_id,
            amount_due=amount_due,
            amount_paid=0,
            status="pending",
            due_date=due_date
        )
        db.add(student_fee)
        student_fees.append(student_fee)
    
    await db.commit()
    
    # Refresh all fees to get updated values
    for fee in student_fees:
        await db.refresh(fee)
    
    return student_fees

@router.get("/student-fees", response_model=List[StudentFeeInDB])
async def get_student_fees(
    student_id: Optional[int] = Query(None),
    fee_type_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get student fees with optional filtering.
    """
    # Start with base query
    query = select(StudentFee)
    
    # Apply filters
    if student_id:
        query = query.where(StudentFee.student_id == student_id)
        
        # Check permissions for viewing student's fees
        student_result = await db.execute(select(Student).where(Student.id == student_id))
        student = student_result.scalars().first()
        
        if student:
            if current_user.role.name != "super_admin" and current_user.school_id != student.school_id:
                # Check if current user is a parent of this student
                is_parent = False
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
                        detail="Not authorized to view fees for students from another school"
                    )
    
    if fee_type_id:
        query = query.where(StudentFee.fee_type_id == fee_type_id)
        
        # Check permissions for viewing fee type
        if current_user.role.name != "super_admin":
            fee_type_result = await db.execute(select(FeeType).where(FeeType.id == fee_type_id))
            fee_type = fee_type_result.scalars().first()
            
            if fee_type and fee_type.school_id != current_user.school_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to view fees for this fee type"
                )
    
    if status:
        query = query.where(StudentFee.status == status)
    
    # Filter by school for regular users
    if not student_id and current_user.role.name != "super_admin":
        query = query.join(Student, StudentFee.student_id == Student.id)
        query = query.where(Student.school_id == current_user.school_id)
    
    # Apply pagination
    query = query.offset(skip).limit(limit)
    
    # Execute query
    result = await db.execute(query)
    fees = result.scalars().all()
    
    return fees

@router.get("/student-fees/{fee_id}", response_model=StudentFeeInDB)
async def get_student_fee(
    fee_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific student fee by ID.
    """
    result = await db.execute(select(StudentFee).where(StudentFee.id == fee_id))
    fee = result.scalars().first()
    
    if not fee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student fee not found"
        )
    
    # Check permissions
    student_result = await db.execute(select(Student).where(Student.id == fee.student_id))
    student = student_result.scalars().first()
    
    if current_user.role.name != "super_admin" and current_user.school_id != student.school_id:
        # Check if current user is a parent of this student
        is_parent = False
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
                detail="Not authorized to view fees for students from another school"
            )
    
    return fee

@router.put("/student-fees/{fee_id}", response_model=StudentFeeInDB)
async def update_student_fee(
    fee_data: StudentFeeUpdate,
    fee_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update a student fee.
    """
    # Check if user has permission to manage student fees
    await validate_admin_access(current_user, db)
    
    # Get fee
    result = await db.execute(select(StudentFee).where(StudentFee.id == fee_id))
    fee = result.scalars().first()
    
    if not fee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student fee not found"
        )
    
    # Check permissions
    student_result = await db.execute(select(Student).where(Student.id == fee.student_id))
    student = student_result.scalars().first()
    
    if current_user.role.name != "super_admin" and current_user.school_id != student.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update fees for students from another school"
        )
    
    # Update fee
    update_data = fee_data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(fee, key, value)
    
    await db.commit()
    await db.refresh(fee)
    
    return fee

@router.get("/student-fees/summary/{student_id}", response_model=FeeSummary)
async def get_fee_summary(
    student_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a summary of fees for a student.
    """
    # Check if student exists
    student_result = await db.execute(select(Student).where(Student.id == student_id))
    student = student_result.scalars().first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found"
        )
    
    # Check permissions
    if current_user.role.name != "super_admin" and current_user.school_id != student.school_id:
        # Check if current user is a parent of this student
        is_parent = False
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
                detail="Not authorized to view fees for students from another school"
            )
    
    # Get all fees for this student
    fees_result = await db.execute(select(StudentFee).where(StudentFee.student_id == student_id))
    fees = fees_result.scalars().all()
    
    # Calculate totals
    total_due = sum(float(fee.amount_due) for fee in fees)
    total_paid = sum(float(fee.amount_paid) for fee in fees)
    total_balance = total_due - total_paid
    
    # Determine overall status
    if total_balance <= 0:
        payment_status = "paid"
    elif total_paid > 0:
        payment_status = "partial"
    elif any(fee.status == "overdue" for fee in fees):
        payment_status = "overdue"
    else:
        payment_status = "pending"
    
    return {
        "total_due": total_due,
        "total_paid": total_paid,
        "total_balance": total_balance,
        "payment_status": payment_status
    }

# Payment endpoints
@router.post("/payments", response_model=PaymentInDB, status_code=status.HTTP_201_CREATED)
async def create_payment(
    payment_data: PaymentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Record a manual payment for a student fee.
    """
    # Check if user has permission to record payments
    await validate_admin_access(current_user, db)
    
    # Validate student fee exists
    fee_result = await db.execute(select(StudentFee).where(StudentFee.id == payment_data.student_fee_id))
    fee = fee_result.scalars().first()
    if not fee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student fee not found"
        )
    
    # Check student to validate school
    student_result = await db.execute(select(Student).where(Student.id == fee.student_id))
    student = student_result.scalars().first()
    
    # Check if user has access to student's school
    if current_user.role.name != "super_admin" and current_user.school_id != student.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to record payments for students from another school"
        )
    
    # Create payment record
    db_payment = Payment(**payment_data.dict())
    db.add(db_payment)
    
    # Update student fee
    fee.amount_paid += payment_data.amount
    
    # Update status
    if float(fee.amount_paid) >= float(fee.amount_due):
        fee.status = "paid"
    else:
        fee.status = "partial"
    
    await db.commit()
    await db.refresh(db_payment)
    
    return db_payment

@router.get("/payments", response_model=List[PaymentInDB])
async def get_payments(
    student_fee_id: Optional[int] = Query(None),
    student_id: Optional[int] = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get payments with optional filtering.
    """
    # Start with base query
    query = select(Payment)
    
    # Apply filters
    if student_fee_id:
        query = query.where(Payment.student_fee_id == student_fee_id)
    
    if student_id:
        # Join with StudentFee to filter by student_id
        query = query.join(StudentFee, Payment.student_fee_id == StudentFee.id)
        query = query.where(StudentFee.student_id == student_id)
        
        # Check permissions
        student_result = await db.execute(select(Student).where(Student.id == student_id))
        student = student_result.scalars().first()
        
        if student and current_user.role.name != "super_admin" and current_user.school_id != student.school_id:
            # Check if current user is a parent of this student
            is_parent = False
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
                    detail="Not authorized to view payments for students from another school"
                )
    
    # Filter by school for regular users if no specific student is requested
    if not student_id and current_user.role.name != "super_admin":
        query = query.join(StudentFee, Payment.student_fee_id == StudentFee.id)
        query = query.join(Student, StudentFee.student_id == Student.id)
        query = query.where(Student.school_id == current_user.school_id)
    
    # Apply pagination
    query = query.offset(skip).limit(limit)
    
    # Execute query
    result = await db.execute(query)
    payments = result.scalars().all()
    
    return payments

@router.post("/payments/paystack/initialize", response_model=PaystackPaymentResponse)
async def initialize_paystack_payment(
    payment_data: PaystackPaymentInit,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Initialize a payment transaction with Paystack.
    """
    # Validate student fee exists
    fee_result = await db.execute(select(StudentFee).where(StudentFee.id == payment_data.student_fee_id))
    fee = fee_result.scalars().first()
    if not fee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student fee not found"
        )
    
    # Check student to validate permissions
    student_result = await db.execute(select(Student).where(Student.id == fee.student_id))
    student = student_result.scalars().first()
    
    # Check if user is authorized to pay for this student
    authorized = False
    if current_user.role.name in ["super_admin", "admin_staff"]:
        authorized = True
    elif current_user.school_id == student.school_id:
        if current_user.role.name == "parent":
            # Check if parent is linked to student
            parent_student_result = await db.execute(
                select(User).join(
                    "student_parents",
                    User.id == student.id
                ).where(User.id == current_user.id)
            )
            is_parent = parent_student_result.scalars().first() is not None
            authorized = is_parent
    
    if not authorized:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to make payments for this student"
        )
    
    # Ensure amount is positive and not more than the balance
    balance = float(fee.amount_due) - float(fee.amount_paid)
    if float(payment_data.amount) <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment amount must be positive"
        )
    
    if float(payment_data.amount) > balance:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Payment amount cannot exceed the balance due ({balance})"
        )
    
    # Initialize payment with Paystack
    try:
        # Get student and fee type information for the payment description
        fee_type_result = await db.execute(select(FeeType).where(FeeType.id == fee.fee_type_id))
        fee_type = fee_type_result.scalars().first()
        
        user_result = await db.execute(select(User).where(User.id == student.user_id))
        user = user_result.scalars().first()
        
        # Create payment description
        description = f"Payment for {fee_type.name} - {user.full_name}"
        
        # Initialize payment
        response = await initialize_payment(
            email=payment_data.email,
            amount=float(payment_data.amount),
            callback_url=payment_data.callback_url,
            reference=f"fee_{fee.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            metadata={
                "student_fee_id": fee.id,
                "student_id": student.id,
                "fee_type": fee_type.name
            },
            description=description
        )
        
        return {
            "authorization_url": response["authorization_url"],
            "access_code": response["access_code"],
            "reference": response["reference"]
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize payment: {str(e)}"
        )

@router.post("/payments/paystack/verify", response_model=PaymentVerificationResponse)
async def verify_paystack_payment(
    verification_data: PaymentVerification,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Verify a Paystack payment and update the student fee accordingly.
    """
    try:
        # Verify the payment with Paystack
        verification_result = await verify_payment(verification_data.reference)
        
        if not verification_result["status"]:
            return {
                "is_successful": False,
                "message": "Payment verification failed"
            }
        
        # Extract student_fee_id from metadata
        student_fee_id = verification_result["metadata"].get("student_fee_id")
        if not student_fee_id:
            return {
                "is_successful": False,
                "message": "Payment metadata does not contain student_fee_id"
            }
        
        # Get the student fee
        fee_result = await db.execute(select(StudentFee).where(StudentFee.id == student_fee_id))
        fee = fee_result.scalars().first()
        
        if not fee:
            return {
                "is_successful": False,
                "message": "Student fee not found"
            }
        
        # Create payment record
        payment = Payment(
            student_fee_id=student_fee_id,
            amount=verification_result["amount"] / 100,  # Paystack amount is in kobo
            payment_method="paystack",
            payment_reference=verification_data.reference
        )
        db.add(payment)
        
        # Update student fee
        fee.amount_paid += payment.amount
        
        # Update status
        if float(fee.amount_paid) >= float(fee.amount_due):
            fee.status = "paid"
        else:
            fee.status = "partial"
        
        await db.commit()
        
        return {
            "is_successful": True,
            "amount": payment.amount,
            "transaction_date": payment.payment_date,
            "message": "Payment verified successfully"
        }
    
    except Exception as e:
        return {
            "is_successful": False,
            "message": f"Error processing payment verification: {str(e)}"
        }
