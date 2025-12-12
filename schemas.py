from pydantic import BaseModel, EmailStr, Field
from datetime import datetime, date
from typing import Optional

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    id: str | None = None
    type: str | None = None
    company_id: str | None = None

class CompanyOut(BaseModel):
    id: int
    name: str
    email: EmailStr
    is_admin: bool
    status: str
    
    # --- CRITICAL FIELDS FOR ADMIN MODAL ---
    business_reg_number: Optional[str] = None
    phone_number: Optional[str] = None # <--- ADDED
    primary_contact_name: Optional[str] = None
    citizenship_number: Optional[str] = None
    # ---------------------------------------

    class Config:
        from_attributes = True

class UserUpdate(BaseModel):
    name: str
    email: EmailStr
    phone_number: str | None = None 

class PasswordChange(BaseModel):
    current_password: str
    new_password: str

class WorkerCreate(BaseModel):
    name: str
    email: EmailStr
    worker_id: str
    role: str = 'member'
    password: str

class WorkerUpdate(BaseModel):
    name: str
    email: EmailStr
    worker_id: str
    role: str

class WorkerOut(BaseModel):
    id: int
    name: str
    email: EmailStr | None
    worker_id: str
    role: str
    status: str
    class Config:
        from_attributes = True

# --- CERTIFICATE SCHEMAS ---
class CertificateOut(BaseModel):
    id: int
    certificate_uid: str
    company_id: int  # <--- ADD THIS LINE
    worker_id: int
    recipient_name: str
    recipient_email: Optional[str] = None
    course_title: str
    course_duration: str | None = None
    completion_date: date 
    issue_date: datetime
    status: str
    sha_hash: str     # <--- Ensure this is present
    verification_count: int | None = 0 # <--- Ensure this is present

    class Config:
        from_attributes = True
        
# --- PASSWORD RESET SCHEMAS ---
class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(..., min_length=6)

# ... inside backend/schemas.py ...

class NotificationSettings(BaseModel):
    notify_issued: bool
    notify_summary: bool
    notify_security: bool
    
