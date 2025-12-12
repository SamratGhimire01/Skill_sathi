# backend/routers/certificates.py

from fastapi import APIRouter, Depends, status, HTTPException, File, UploadFile, Form, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List
from datetime import date, datetime
import uuid, hashlib, io, csv, codecs
from fastapi import BackgroundTasks
from utils.notifications import send_email_real
from utils.notifications import trigger_certificate_email, trigger_recipient_certificate

import models, schemas
from database import get_db
from . import auth
from utils.pdf_generator import generate_certificate_pdf

router = APIRouter(prefix="/certificates", tags=['Certificates'])

# --- HELPER: Get Company Branding ---
def get_branding(db: Session, company_id: int):
    company = db.query(models.Company).filter(models.Company.id == company_id).first()
    if company:
        return {
            'logo_bytes': company.logo,
            'signature_bytes': company.signature_image
        }
    return None

# --- 1. ISSUE CERTIFICATE (Single) ---
@router.post("/", status_code=status.HTTP_201_CREATED, response_model=schemas.CertificateOut)
async def issue_certificate(
    background_tasks: BackgroundTasks,
    recipient_name: str = Form(...),
    recipient_email: str = Form(...),
    course_title: str = Form(...),
    completion_date: date = Form(...),
    course_duration: str = Form(""),
    recipient_photo: UploadFile = File(None),
    db: Session = Depends(get_db),
    token: str = Depends(auth.oauth2_scheme)
):
    user = auth.get_current_user_role(token)
    user_id, user_type = int(user['id']), user['type']
    
    company_id, worker_id = None, None
    cert_status = 'pending_approval'

    # Auto-approve if Company Admin
    if user_type == 'company':
        company_id = user_id
        cert_status = 'active'
        worker = db.query(models.Worker).filter(models.Worker.company_id == company_id).first()
        worker_id = worker.id if worker else 0 
        actor_desc = "Company Admin"
    elif user_type == 'worker':
        worker = db.query(models.Worker).filter(models.Worker.id == user_id).first()
        company_id, worker_id = worker.company_id, worker.id
        cert_status = 'pending_approval'
        actor_desc = f"Staff {worker.name}"

    # Generate Data
    cert_uid = f"SKSL-{uuid.uuid4().hex[:8].upper()}"
    sha_hash = hashlib.sha256(f"{cert_uid}-{recipient_name}".encode()).hexdigest()
    photo_data = await recipient_photo.read() if recipient_photo else None
    
    # --- FETCH BRANDING ---
    branding = get_branding(db, company_id)

    # Create PDF
    pdf_data_dict = {
        "recipient_name": recipient_name,
        "course_title": course_title,
        "completion_date": completion_date,
        "certificate_uid": cert_uid,
        "recipient_photo": photo_data,
        "course_duration": course_duration,  # <--- PASS DURATION
        "sha_hash": sha_hash
    }
    
    # Generate (Pass branding here)
    pdf_bytes = generate_certificate_pdf(
        pdf_data_dict, 
        is_preview=(cert_status == 'pending_approval'),
        company_branding=branding 
    )

    new_cert = models.Certificate(
        certificate_uid=cert_uid,
        company_id=company_id,
        worker_id=worker_id,
        recipient_name=recipient_name,
        recipient_email=recipient_email,
        course_title=course_title,
        course_duration=course_duration,
        completion_date=completion_date,
        sha_hash=sha_hash,
        recipient_photo=photo_data,
        pdf_data=pdf_bytes,
        status=cert_status 
    )
    
    db.add(new_cert)
    db.commit()
    
    # Log
    db.add(models.AuditLog(
        company_id=company_id, 
        actor_type="company" if user_type == 'company' else "staff", 
        actor_id=user_id, 
        cert_id=new_cert.id,
        event_type="issue_certificate", 
        details=f"Issued by {actor_desc} to {recipient_name} ({cert_status})"
    ))
    db.commit()

    # --- PASTE YOUR CODE HERE ---
    # Trigger Email Notification (Background Task)
    comp = db.query(models.Company).filter(models.Company.id == company_id).first()
    if comp:
        trigger_certificate_email(
            background_tasks, 
            comp.email, 
            recipient_name, 
            comp.notify_issued
        )
    # ---------------------------
    
    return new_cert

# --- 2. BULK IMPORT ---
@router.post("/bulk-import")
async def bulk_import_certificates(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    token: str = Depends(auth.oauth2_scheme)
):
    user = auth.get_current_user_role(token)
    user_id, user_type = int(user['id']), user['type']
    
    if user_type == 'worker':
        worker = db.query(models.Worker).filter(models.Worker.id == user_id).first()
        company_id, worker_id = worker.company_id, worker.id
        status_default = 'pending_approval'
    elif user_type == 'company':
        company_id = user_id
        w = db.query(models.Worker).filter(models.Worker.company_id == company_id).first()
        worker_id = w.id if w else 0
        status_default = 'active'
    else:
        raise HTTPException(status_code=403, detail="Unauthorized role")

    try:
        csvReader = csv.reader(codecs.iterdecode(file.file, 'utf-8'))
        header = next(csvReader) 
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid CSV file")

    # Fetch Branding once for the batch
    branding = get_branding(db, company_id)
    count = 0
    
    for row in csvReader:
        if len(row) < 4: continue
        name, email, course, duration = row[0], row[1], row[2],row[3]
        if not name or not course: continue

        cert_uid = f"SKSL-{uuid.uuid4().hex[:8].upper()}"
        sha_hash = hashlib.sha256(f"{cert_uid}-{name}".encode()).hexdigest()
        
        pdf_data = {
            "recipient_name": name,
            "course_title": course,
            "course_duration": duration,
            "completion_date": date.today(),
            "certificate_uid": cert_uid,
            "recipient_photo": None
        }
        
        # Generate with Branding
        pdf_bytes = generate_certificate_pdf(
            pdf_data, 
            is_preview=(status_default == 'pending_approval'),
            company_branding=branding
        )

        new_cert = models.Certificate(
            certificate_uid=cert_uid,
            company_id=company_id,
            worker_id=worker_id,
            recipient_name=name,
            recipient_email=email,
            course_title=course,
            completion_date=date.today(),
            sha_hash=sha_hash,
            pdf_data=pdf_bytes,
            status=status_default
        )
        db.add(new_cert)
        count += 1

    db.commit()
    return {"message": f"Successfully processed {count} certificates."}

# --- 3. GET CERTIFICATES ---
@router.get("/", response_model=List[schemas.CertificateOut])
def get_certificates(db: Session = Depends(get_db), token: str = Depends(auth.oauth2_scheme)):
    user = auth.get_current_user_role(token)
    uid, utype = int(user['id']), user['type']
    
    query = db.query(models.Certificate)
    
    if utype == 'worker':
        # CRITICAL FIX: Workers only see certificates THEY issued (worker_id filter)
        query = query.filter(models.Certificate.worker_id == uid)
    else:
        # Company Admins see all for their company (company_id filter)
        cid = int(user.get('company_id') or uid)
        query = query.filter(models.Certificate.company_id == cid)
        
    return query.order_by(models.Certificate.issue_date.desc()).all()

# --- 4. PREVIEW CERTIFICATE ---
@router.get("/{cert_id}/preview")
def preview_certificate(cert_id: int, db: Session = Depends(get_db), token: str = Depends(auth.oauth2_scheme)):
    cert = db.query(models.Certificate).filter(models.Certificate.id == cert_id).first()
    if not cert: raise HTTPException(status_code=404, detail="Not found")
    
    # If pending, REGENERATE PDF with watermark AND branding
    if cert.status == 'pending_approval':
        branding = get_branding(db, cert.company_id)
        data = {
            "recipient_name": cert.recipient_name,
            "course_title": cert.course_title,
            "completion_date": cert.completion_date,
            "certificate_uid": cert.certificate_uid,
            "recipient_photo": cert.recipient_photo
        }
        # Force regen to show updated branding
        pdf_bytes = generate_certificate_pdf(data, is_preview=True, company_branding=branding)
        return StreamingResponse(io.BytesIO(pdf_bytes), media_type="application/pdf", headers={"Content-Disposition": "inline"})
    else:
        if not cert.pdf_data: raise HTTPException(404, "PDF data missing")
        return StreamingResponse(io.BytesIO(cert.pdf_data), media_type="application/pdf", headers={"Content-Disposition": "inline"})

# --- 5. DOWNLOAD PDF ---
@router.get("/{cert_id}/pdf")
def download_pdf(cert_id: int, db: Session = Depends(get_db)):
    cert = db.query(models.Certificate).filter(models.Certificate.id == cert_id).first()
    if not cert or not cert.pdf_data: raise HTTPException(status_code=404, detail="PDF not found")
    return StreamingResponse(io.BytesIO(cert.pdf_data), media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="{cert.certificate_uid}.pdf"'})

# --- 6. APPROVE ENDPOINT ---
@router.post("/approve")
def approve_certificates(
    cert_ids: List[int],
    db: Session = Depends(get_db),
    current_company: models.Company = Depends(auth.get_current_company)
):
    certs_to_approve = db.query(models.Certificate).filter(
        models.Certificate.id.in_(cert_ids),
        models.Certificate.company_id == current_company.id,
        models.Certificate.status == 'pending_approval'
    ).all()
    
    branding = get_branding(db, current_company.id)
    count = 0
    
    for cert in certs_to_approve:
        cert.status = 'active'
        data = {
            "recipient_name": cert.recipient_name,
            "course_title": cert.course_title,
            "completion_date": cert.completion_date,
            "certificate_uid": cert.certificate_uid,
            "recipient_photo": cert.recipient_photo
        }
        # Regenerate FINAL PDF with Branding
        cert.pdf_data = generate_certificate_pdf(data, is_preview=False, company_branding=branding)
        count += 1
        
    db.commit()
    return {"message": f"Successfully approved {count} certificates."}

# --- 7. REVOKE & DELETE (Standard) ---
@router.post("/{cert_id}/revoke")
def revoke_certificate(cert_id: int, db: Session = Depends(get_db), current_company: models.Company = Depends(auth.get_current_company)):
    cert = db.query(models.Certificate).filter(models.Certificate.id == cert_id, models.Certificate.company_id == current_company.id).first()
    if not cert: raise HTTPException(404, "Not found")
    cert.status = 'revoked'
    db.commit()
    return {"message": "Revoked"}

@router.delete("/{cert_id}")
def delete_certificate(cert_id: int, confirm_name: str = Form(...), db: Session = Depends(get_db), token: str = Depends(auth.oauth2_scheme)):
    cert = db.query(models.Certificate).filter(models.Certificate.id == cert_id).first()
    if not cert: raise HTTPException(404, "Not found")
    if cert.recipient_name.lower().strip() != confirm_name.lower().strip(): raise HTTPException(400, "Name mismatch")
    db.delete(cert)
    db.commit()
    return {"message": "Deleted"}

# 8. NEW: SEND CERTIFICATE TO RECIPIENT
@router.post("/{cert_id}/send-email")
def send_certificate_email(
    cert_id: int, 
    background_tasks: BackgroundTasks, 
    db: Session = Depends(get_db), 
    current_company: models.Company = Depends(auth.get_current_company)
):
    cert = db.query(models.Certificate).filter(
        models.Certificate.id == cert_id,
        models.Certificate.company_id == current_company.id,
        models.Certificate.status == 'active' # Only send active certificates
    ).first()

    if not cert or not cert.pdf_data:
        raise HTTPException(status_code=404, detail="Certificate not found or PDF data is missing.")
        
    if not cert.recipient_email:
        raise HTTPException(status_code=400, detail="Recipient email is missing.")

    # 1. Prepare Data for Email
    cert_data_dict = {
        'recipient_name': cert.recipient_name,
        'recipient_email': cert.recipient_email,
        'course_title': cert.course_title,
        'certificate_uid': cert.certificate_uid,
        'sha_hash': cert.sha_hash
    }

    # 2. Trigger the Send (with PDF attachment)
    trigger_recipient_certificate(
        background_tasks,
        cert_data=cert_data_dict,
        pdf_data=cert.pdf_data
    )

    return {"message": f"Certificate sent to {cert.recipient_email}"}