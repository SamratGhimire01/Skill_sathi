# backend/routers/admin.py

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime
from typing import List
import io

import models, schemas
from database import get_db
from . import auth

router = APIRouter(prefix="/admin", tags=['Super Admin'])

# --- DEPENDENCY: Check if user is Super Admin ---
def get_super_admin(current_company: models.Company = Depends(auth.get_current_company)):
    if not current_company.is_admin:
        raise HTTPException(status_code=403, detail="Super Admin Access Only")
    return current_company

# 1. GET DASHBOARD STATS
@router.get("/stats")
def get_stats(db: Session = Depends(get_db), admin=Depends(get_super_admin)):
    
    # COUNT 1: Total Centers
    total_centers = db.query(models.Company).count()
    
    # COUNT 2: Total Certificates (Platform-wide)
    total_cert = db.query(models.Certificate).count()
    
    # COUNT 3: Total Workers (Platform-wide)
    total_workers = db.query(models.Worker).count() 
    
    # COUNT 4: PENDING REVIEWS (CRITICAL FIX)
    # This must query the 'companies' table for status='pending'
    pending_reviews = db.query(models.Company).filter(models.Company.status == 'pending').count()
    
    return {
        "total_centers": total_centers,
        "total_certificates": total_cert,
        "total_workers": total_workers,
        "pending_reviews": pending_reviews # <--- THIS VALUE IS NOW CORRECT
    }

# 2. NEW: GET CHART DATA (Monthly Issuance & Center Status)
@router.get("/charts/data")
def get_admin_chart_data(db: Session = Depends(get_db), admin=Depends(get_super_admin)):
    # --- A. Monthly Issuance Data (Bar Chart) ---
    monthly_counts = [0] * 12
    current_year = datetime.utcnow().year
    
    certs = db.query(models.Certificate).filter(
        func.extract('year', models.Certificate.issue_date) == current_year
    ).all()
    
    for c in certs:
        if c.issue_date:
            monthly_counts[c.issue_date.month - 1] += 1

    # --- B. Center Status Data (Pie Chart) ---
    status_counts = db.query(
        models.Company.status, 
        func.count(models.Company.id)
    ).group_by(models.Company.status).all()

    center_status = {status: count for status, count in status_counts}
            
    return {
        "monthly_issuance": monthly_counts,
        "center_status": center_status
    }

# 3. GET SYSTEM LOGS (Existing)
@router.get("/logs")
def get_logs(db: Session = Depends(get_db), admin=Depends(get_super_admin)):
    # Get last 50 logs
    logs = db.query(models.AuditLog).order_by(models.AuditLog.timestamp.desc()).limit(50).all()

    # CRITICAL: Prepare a map of worker IDs to Names (Efficiently)
    worker_ids = [log.actor_id for log in logs if log.actor_type == 'staff' and log.actor_id is not None]
    
    # Query all necessary worker names in one go
    workers = db.query(models.Worker).filter(models.Worker.id.in_(worker_ids)).all()
    worker_map = {w.id: w.name for w in workers}
    
    # Format the logs
    formatted_logs = []
    for log in logs:
        # Default display is actor_type
        actor_display = log.actor_type
        
        # Override if it's a staff member
        if log.actor_type == 'staff' and log.actor_id in worker_map:
            worker_name = worker_map[log.actor_id]
            actor_display = f"Staff: {worker_name}"
        elif log.actor_type == 'company':
            actor_display = f"Admin: Company {log.company_id}"
            
        formatted_logs.append({
            "timestamp": log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "event_type": log.event_type,
            "actor_id": log.actor_id,
            "details": log.details,
            "actor_display": actor_display # <--- NEW FIELD FOR FRONTEND
        })

    return formatted_logs

# 4. LIST ALL COMPANIES (Existing)
@router.get("/companies", response_model=List[schemas.CompanyOut])
def list_companies(db: Session = Depends(get_db), admin=Depends(get_super_admin)):
    return db.query(models.Company).all()

# 5. GET SINGLE COMPANY DETAILS + STATS (Existing)
@router.get("/companies/{company_id}/details")
def get_company_details(company_id: int, db: Session = Depends(get_db), admin=Depends(get_super_admin)):
    company = db.query(models.Company).filter(models.Company.id == company_id).first()
    if not company: 
        raise HTTPException(status_code=404, detail="Company not found")
    
    safe_company_data = schemas.CompanyOut.from_orm(company).dict()
    
    worker_count = db.query(models.Worker).filter(models.Worker.company_id == company_id).count()
    cert_count = db.query(models.Certificate).filter(models.Certificate.company_id == company_id).count()
    cert_active = db.query(models.Certificate).filter(models.Certificate.company_id == company_id, models.Certificate.status == 'active').count()
    
    return {
        "company": safe_company_data,
        "stats": {
            "workers": worker_count,
            "certificates": cert_count,
            "active_certs": cert_active,
        }
    }

# 6. SERVE DOCUMENTS (Existing)
@router.get("/companies/{company_id}/files/{file_type}")
def get_company_file(
    company_id: int, 
    file_type: str, 
    db: Session = Depends(get_db), 
    admin: models.Company = Depends(get_super_admin)
):
    company = db.query(models.Company).filter(models.Company.id == company_id).first()
    if not company: raise HTTPException(status_code=404, detail="Company not found")
    
    file_data = company.contact_photo if file_type == 'photo' else company.registration_document
            
    if not file_data: raise HTTPException(status_code=404, detail="File not found")
    
    # --- LOGIC TO DETERMINE MEDIA TYPE ---
    media_type = "image/jpeg" # Default to JPEG/PNG for images
    
    # Check for PDF signature
    if file_data.startswith(b'%PDF'):
        media_type = "application/pdf"
    # ------------------------------------
    
    # For Images, we want the browser to display it as a standard image.
    # For PDFs, we want the browser to display it as an application/pdf (with scrollbars/zoom).

    return StreamingResponse(io.BytesIO(file_data), media_type=media_type)

# 7. APPROVE COMPANY (Existing)
@router.put("/companies/{company_id}/approve")
def approve_company(company_id: int, db: Session = Depends(get_db), admin=Depends(get_super_admin)):
    company = db.query(models.Company).filter(models.Company.id == company_id).first()
    if not company: raise HTTPException(status_code=404, detail="Not found")
    company.status = 'verified'
    db.commit()
    return {"message": "Company verified."}

# 8. DELETE COMPANY (Existing)
@router.delete("/companies/{company_id}")
def delete_company(company_id: int, db: Session = Depends(get_db), admin=Depends(get_super_admin)):
    company = db.query(models.Company).filter(models.Company.id == company_id).first()
    if not company: raise HTTPException(status_code=404, detail="Not found")
    if company.id == 1: raise HTTPException(status_code=403, detail="Cannot delete the main SkillSathi HQ account.")
    db.delete(company)
    db.commit()
    return {"message": "Company deleted."}

# 9. RESOLVE TICKET (Existing)
@router.get("/tickets") # <--- Admin router handles /admin/tickets
def get_all_tickets(
    db: Session = Depends(get_db),
    current_company: models.Company = Depends(auth.get_current_company)
):
    if not current_company.is_admin:
        raise HTTPException(status_code=403, detail="Admin only")
    
    # Fetch tickets and JOIN to get company name
    tickets = db.query(models.SupportTicket).order_by(models.SupportTicket.created_at.desc()).all()
    
    result = []
    for t in tickets:
        comp = db.query(models.Company).filter(models.Company.id == t.company_id).first()
        result.append({
            "id": t.id,
            "subject": t.subject,
            "message": t.message,
            "status": t.status,
            "created_at": t.created_at,
            "company_name": comp.name if comp else "Unknown"
        })
    return result

# 8. RESOLVE TICKET (For Super Admin)
@router.put("/tickets/{ticket_id}/resolve")
def resolve_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_company: models.Company = Depends(auth.get_current_company)
):
    if not current_company.is_admin:
        raise HTTPException(status_code=403, detail="Admin only")
        
    ticket = db.query(models.SupportTicket).filter(models.SupportTicket.id == ticket_id).first()
    if ticket:
        ticket.status = 'resolved'
        db.commit()
    return {"message": "Marked as resolved"}