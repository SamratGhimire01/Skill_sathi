# backend/routers/verification.py

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import models, schemas
from database import get_db
import io

router = APIRouter(prefix="/verification", tags=['Public Verification'])

# Update the response model to include 'sha_hash'
@router.get("/{certificate_uid}", response_model=schemas.CertificateOut) 
def verify_certificate(certificate_uid: str, db: Session = Depends(get_db)):
    
    # 1. Search for the certificate by its Unique ID (UID) or SHA hash
    certificate = db.query(models.Certificate).filter(
        (models.Certificate.certificate_uid == certificate_uid) |
        (models.Certificate.sha_hash == certificate_uid)
    ).first()

    if not certificate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Certificate not found. The ID or hash is invalid."
        )
    
    # --- CRITICAL FIX: Block Verification if still pending ---
    if certificate.status == 'pending_approval':
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="The certificate is not yet active in the public ledger."
        )

    # Increment verification count
    certificate.verification_count += 1
    db.commit() 
    
    # Return the full schema, which includes sha_hash.
    return certificate

# --- DOWNLOAD PUBLIC PDF (FIXED ENDPOINT) ---
@router.get("/{certificate_uid}/download")
def download_public_pdf(certificate_uid: str, db: Session = Depends(get_db)):
    
    # 1. Find Certificate
    cert = db.query(models.Certificate).filter(
        models.Certificate.certificate_uid == certificate_uid
    ).first()

    if not cert or not cert.pdf_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PDF file not found for this ID.")
    
    if cert.status == 'revoked':
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Certificate is revoked.")

    # 2. Return PDF as a stream
    return StreamingResponse(
        io.BytesIO(cert.pdf_data), 
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{cert.certificate_uid}.pdf"'}
    )