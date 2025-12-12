from sqlalchemy import (
    Column, Integer, String, Boolean, ForeignKey, Date, LargeBinary, 
    Enum, TIMESTAMP, TEXT, DECIMAL, text
)
from sqlalchemy.dialects.mysql import LONGBLOB
from sqlalchemy.orm import relationship 
from database import Base
from datetime import datetime

class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    business_reg_number = Column(String(100))
    
    # --- BASIC COMPANY DATA ---
    status = Column(Enum('pending', 'verified', 'rejected'), default='pending')
    subscription_tier = Column(Enum('free', 'basic', 'medium', 'pro'), default='free')
    certificates_used = Column(Integer, default=0)
    business_address = Column(String(255))
    phone_number = Column(String(20))
    website_url = Column(String(255))
    is_admin = Column(Boolean, default=False)
    created_at = Column(TIMESTAMP, server_default=text('CURRENT_TIMESTAMP'))
    
    # --- CONTACT/REGISTRATION FIELDS ---
    primary_contact_name = Column(String(255))
    citizenship_number = Column(String(100))
    contact_photo = Column(LONGBLOB)
    registration_document = Column(LONGBLOB)
    
    # --- BRANDING/ASSETS (DEFINED ONLY ONCE) ---
    logo = Column(LargeBinary, nullable=True)         # <-- DEFINED ONCE
    signature_image = Column(LargeBinary, nullable=True) # <-- DEFINED ONCE
    
    # --- NOTIFICATION PREFERENCES ---
    notify_issued = Column(Boolean, default=True)
    notify_summary = Column(Boolean, default=False)
    notify_security = Column(Boolean, default=True)



class Worker(Base):
    __tablename__ = "workers"
    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    email = Column(String(255))
    worker_id = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255))
    role = Column(Enum('owner', 'admin', 'manager', 'member'), default='member')
    status = Column(Enum('active', 'pending', 'suspended'), default='active')
    profile_picture = Column(LargeBinary)
    phone_number = Column(String(20))
    date_of_birth = Column(Date)
    address = Column(TEXT)
    created_at = Column(TIMESTAMP, server_default=text('CURRENT_TIMESTAMP'))

class Certificate(Base):
    __tablename__ = "certificates"
    id = Column(Integer, primary_key=True, autoincrement=True)
    certificate_uid = Column(String(100), unique=True, nullable=False)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    worker_id = Column(Integer, ForeignKey("workers.id", ondelete="CASCADE"), nullable=False)
    recipient_name = Column(String(255), nullable=False)
    recipient_email = Column(String(255))
    recipient_photo = Column(LargeBinary)
    course_title = Column(String(255), nullable=False)
    course_category = Column(String(100))
    course_duration = Column(String(100), nullable=True)
    completion_date = Column(Date, nullable=False)
    issue_date = Column(TIMESTAMP, server_default=text('CURRENT_TIMESTAMP'))
    sha_hash = Column(String(64), unique=True, nullable=False)
    status = Column(Enum('active', 'revoked', 'expired', 'pending_approval'), default='pending_approval')
    qr_code = Column(LargeBinary)
    download_count = Column(Integer, default=0) 
    verification_count = Column(Integer, default=0) 
    pdf_data = Column(LargeBinary)
    created_at = Column(TIMESTAMP, server_default=text('CURRENT_TIMESTAMP'))
    
class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"))
    user_id = Column(Integer, ForeignKey("workers.id", ondelete="SET NULL"))
    actor_type = Column(Enum('company', 'staff', 'public', 'system'), nullable=False)
    actor_id = Column(Integer)
    cert_id = Column(Integer, ForeignKey("certificates.id", ondelete="SET NULL"))
    event_type = Column(String(100))
    details = Column(TEXT)
    timestamp = Column(TIMESTAMP, server_default=text('CURRENT_TIMESTAMP'))

class SharedCertificate(Base):
    __tablename__ = "shared_certificates"
    id = Column(Integer, primary_key=True, autoincrement=True)
    cert_id = Column(Integer, ForeignKey("certificates.id", ondelete="CASCADE"), nullable=False)
    token = Column(String(100), unique=True, nullable=False)
    created_at = Column(TIMESTAMP, server_default=text('CURRENT_TIMESTAMP'))
    expires_at = Column(TIMESTAMP, nullable=True)
    is_active = Column(Boolean, default=True)
    
class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    subject = Column(String(255), nullable=False)
    message = Column(TEXT, nullable=False)
    status = Column(Enum('open', 'resolved'), default='open')
    created_at = Column(TIMESTAMP, server_default=text('CURRENT_TIMESTAMP'))
    
    # Relationship to fetch company name easily
    company = relationship("Company")