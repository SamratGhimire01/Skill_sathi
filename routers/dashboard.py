# backend/routers/dashboard.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from datetime import datetime
import models
from database import get_db
from . import auth

router = APIRouter(prefix="/dashboard", tags=['Dashboard'])

# 1. DASHBOARD STATS
@router.get("/stats")
def get_dashboard_stats(db: Session = Depends(get_db), token: str = Depends(auth.oauth2_scheme)):
    user = auth.get_current_user_role(token)
    user_id = int(user['id'])
    user_type = user['type']
    
    if user_type == 'company':
        cid = int(user.get('company_id') or user_id)
        
        total_workers = db.query(models.Worker).filter(models.Worker.company_id == cid).count()
        active_certs = db.query(models.Certificate).filter(models.Certificate.company_id == cid, models.Certificate.status == 'active').count()
        pending_certs = db.query(models.Certificate).filter(models.Certificate.company_id == cid, models.Certificate.status == 'pending_approval').count()
        
        # Recent logs for widget
        logs = db.query(models.AuditLog).filter(models.AuditLog.company_id == cid).order_by(models.AuditLog.timestamp.desc()).limit(5).all()
                 
        return {
            "role": "company",
            "total_workers": total_workers,
            "total_certs": active_certs,
            "pending_count": pending_certs,
            "recent_logs": logs
        }
    
    elif user_type == 'worker':
        total = db.query(models.Certificate).filter(models.Certificate.worker_id == user_id).count()
        pending = db.query(models.Certificate).filter(models.Certificate.worker_id == user_id, models.Certificate.status == 'pending_approval').count()
        return {"role": "worker", "total_issued": total, "pending_count": pending}
        
    return {}

# 2. CHART DATA
@router.get("/chart")
def get_role_based_chart(db: Session = Depends(get_db), token: str = Depends(auth.oauth2_scheme)):
    user = auth.get_current_user_role(token)
    cid = int(user.get('company_id') or user['id'])
    
    monthly_counts = [0] * 12
    current_year = datetime.utcnow().year
    
    certs = db.query(models.Certificate).filter(
        models.Certificate.company_id == cid,
        func.extract('year', models.Certificate.issue_date) == current_year
    ).all()
    
    for c in certs:
        if c.issue_date:
            monthly_counts[c.issue_date.month - 1] += 1
            
    return {"data": monthly_counts}

# 3. AUDIT LOGS (FIXED ENDPOINT)
@router.get("/audit-logs")
def get_audit_logs(db: Session = Depends(get_db), token: str = Depends(auth.oauth2_scheme)):
    user = auth.get_current_user_role(token)
    user_type = user['type']
    cid = int(user.get('company_id') or user['id'])

    if user_type == 'company':
        # Get logs for company OR its staff
        return db.query(models.AuditLog).filter(
            models.AuditLog.company_id == cid
        ).order_by(models.AuditLog.timestamp.desc()).limit(100).all()
    
    return []