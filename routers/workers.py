# backend/routers/workers.py (FINAL, CORRECTED VERSION)

from fastapi import APIRouter, Depends, status, HTTPException, Response, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
import models, schemas, os
from database import get_db
from . import auth
from datetime import datetime
from utils.notifications import trigger_worker_onboarding

router = APIRouter(prefix="/workers", tags=['Workers'])

# 1. CREATE WORKER (FIXED company_id = None ERROR)
@router.post("/", status_code=status.HTTP_201_CREATED, response_model=schemas.WorkerOut)
def create_worker(
    worker: schemas.WorkerCreate, 
    background_tasks: BackgroundTasks, 
    db: Session = Depends(get_db), 
    current_company: models.Company = Depends(auth.get_current_company)
):
    
    existing_worker = db.query(models.Worker).filter(models.Worker.worker_id == worker.worker_id).first()
    if existing_worker:
        raise HTTPException(status_code=409, detail="Worker ID already exists.")

    hashed_pwd = auth.hash_password(worker.password)
    temp_password = worker.password 
    
    new_worker = models.Worker(
        # --- CRITICAL FIX ---
        company_id=current_company.id, 
        # --------------------
        name=worker.name,
        email=worker.email,
        worker_id=worker.worker_id,
        role=worker.role,
        password_hash=hashed_pwd
    )
    db.add(new_worker)
    db.commit()
    db.refresh(new_worker)
    
    # Audit Log and Email Trigger
    db.add(models.AuditLog(company_id=current_company.id, actor_type="company", actor_id=current_company.id, event_type="create_worker", details=f"Created worker {worker.name}"))
    db.commit()

    if new_worker.email:
        trigger_worker_onboarding(
            background_tasks,
            worker_email=new_worker.email,
            worker_name=new_worker.name,
            worker_id=new_worker.worker_id,
            temp_password=temp_password
        )

    return new_worker

# ... (rest of the file remains the same) ...

# 2. GET ALL WORKERS
@router.get("/", response_model=List[schemas.WorkerOut])
def get_workers(db: Session = Depends(get_db), current_company: models.Company = Depends(auth.get_current_company)):
    return db.query(models.Worker).filter(models.Worker.company_id == current_company.id).all()

# 3. GET SINGLE WORKER
@router.get("/{worker_id}", response_model=schemas.WorkerOut)
def get_worker(worker_id: int, db: Session = Depends(get_db), current_company: models.Company = Depends(auth.get_current_company)):
    worker = db.query(models.Worker).filter(models.Worker.id == worker_id, models.Worker.company_id == current_company.id).first()
    if not worker: raise HTTPException(status_code=404, detail="Worker not found")
    return worker

# 4. UPDATE WORKER (Fixes 405 error)
@router.put("/{worker_id}", response_model=schemas.WorkerOut)
def update_worker(worker_id: int, worker_update: schemas.WorkerUpdate, db: Session = Depends(get_db), current_company: models.Company = Depends(auth.get_current_company)):
    worker = db.query(models.Worker).filter(models.Worker.id == worker_id, models.Worker.company_id == current_company.id).first()
    if not worker: raise HTTPException(status_code=404, detail="Worker not found")

    worker.name = worker_update.name
    worker.email = worker_update.email
    worker.role = worker_update.role
    
    db.commit()
    db.refresh(worker)
    return worker

# 5. DELETE WORKER
@router.delete("/{worker_id}", status_code=204)
def delete_worker(worker_id: int, db: Session = Depends(get_db), current_company: models.Company = Depends(auth.get_current_company)):
    worker = db.query(models.Worker).filter(models.Worker.id == worker_id, models.Worker.company_id == current_company.id).first()
    if not worker: raise HTTPException(status_code=404, detail="Worker not found")
    
    db.delete(worker)
    db.commit()
    return Response(status_code=204)

# 6. GET WORKER'S OWN AUDIT LOGS
@router.get("/me/logs")
def get_my_audit_logs(
    db: Session = Depends(get_db), 
    current_worker: models.Worker = Depends(auth.get_current_worker)
):
    
    logs = db.query(models.AuditLog).filter(
        models.AuditLog.actor_type == 'staff',
        models.AuditLog.actor_id == current_worker.id
    ).order_by(models.AuditLog.timestamp.desc()).limit(10).all()
    
    formatted_logs = []
    for log in logs:
        formatted_logs.append({
            "timestamp": log.timestamp.strftime("%b %d, %I:%M %p"),
            "event_type": log.event_type,
            "details": log.details
        })
        
    return formatted_logs