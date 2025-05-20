# Import all models to ensure they're registered with SQLAlchemy
from app.models.users import User, Role, Permission, RolePermission
from app.models.schools import School, Department, Class, Subject, AuthenticLocation
from app.models.academics import AcademicSession, Term, Assessment, StudentAssessmentScore
from app.models.attendance import AttendanceRecord
from app.models.finance import FeeType, StudentFee, Payment
from app.models.communication import Message, BehaviorReport, AuditLog
