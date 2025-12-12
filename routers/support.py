from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List
from datetime import datetime

import models, schemas
from database import get_db
from . import auth

router = APIRouter(prefix="/support", tags=['Support']) 

# --- SCHEMAS ---
class TicketCreate(BaseModel):
    subject: str
    message: str

class TicketOut(BaseModel):
    id: int
    subject: str
    message: str
    status: str
    created_at: datetime
    company_name: str | None = None # For Admin View

# --- 1. SUBMIT TICKET (For Companies) ---
@router.post("/submit")
def submit_ticket(
    ticket: TicketCreate,
    db: Session = Depends(get_db),
    current_company: models.Company = Depends(auth.get_current_company)
):
    new_ticket = models.SupportTicket(
        company_id=current_company.id,
        subject=ticket.subject,
        message=ticket.message
    )
    db.add(new_ticket)
    db.commit()
    return {"message": "Ticket submitted successfully. Support team will contact you."}

# --- 2. VIEW ALL TICKETS (For Super Admin) ---
@router.get("/admin/tickets")
def get_all_tickets(
    db: Session = Depends(get_db),
    current_company: models.Company = Depends(auth.get_current_company)
):
    if not current_company.is_admin:
        raise HTTPException(status_code=403, detail="Admin only")
    
    tickets = db.query(models.SupportTicket).order_by(models.SupportTicket.created_at.desc()).all()
    
    # Format response to include company name
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

# --- 3. RESOLVE TICKET (For Super Admin) ---
@router.put("/admin/tickets/{ticket_id}/resolve")
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