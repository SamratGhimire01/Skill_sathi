# backend/routers/companies.py

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Response,status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import io
import models, schemas
from database import get_db
from . import auth

router = APIRouter(prefix="/companies", tags=['Companies'])

# 1. Get Profile
@router.get("/me", response_model=schemas.CompanyOut)
def get_my_profile(current_company: models.Company = Depends(auth.get_current_company)):
    return current_company

# 2. Update Profile (Now includes Phone)
@router.put("/me/profile")
def update_profile(
    data: schemas.UserUpdate, 
    db: Session = Depends(get_db),
    current_company: models.Company = Depends(auth.get_current_company)
):
    current_company.name = data.name
    current_company.email = data.email
    if data.phone_number:
        current_company.phone_number = data.phone_number
        
    db.commit()
    return {"message": "Profile updated successfully"}

# 3. Update Branding
@router.post("/me/branding")
async def update_branding(
    logo: UploadFile = File(None),
    signature: UploadFile = File(None),
    db: Session = Depends(get_db),
    current_company: models.Company = Depends(auth.get_current_company)
):
    if logo:
        current_company.logo = await logo.read()
    if signature:
        current_company.signature_image = await signature.read()
    
    db.commit()
    return {"message": "Branding updated."}

# 4. NEW: Serve Branding Images (For Frontend Preview)
@router.get("/me/branding/{image_type}")
def get_branding_image(image_type: str, current_company: models.Company = Depends(auth.get_current_company)):
    img_data = None
    if image_type == 'logo':
        img_data = current_company.logo
    elif image_type == 'signature':
        img_data = current_company.signature_image
    
    if not img_data:
        # Return a 1x1 transparent pixel if no image exists to avoid 404 errors in frontend
        return Response(content=b"", media_type="image/png")

    return StreamingResponse(io.BytesIO(img_data), media_type="image/png")

# 5. Notifications (Get/Set)
@router.get("/me/notifications", response_model=schemas.NotificationSettings)
def get_notifications(current_company: models.Company = Depends(auth.get_current_company)):
    return {
        "notify_issued": current_company.notify_issued,
        "notify_summary": current_company.notify_summary,
        "notify_security": current_company.notify_security
    }

@router.put("/me/notifications")
def update_notifications(
    data: schemas.NotificationSettings,
    db: Session = Depends(get_db),
    current_company: models.Company = Depends(auth.get_current_company)
):
    current_company.notify_issued = data.notify_issued
    current_company.notify_summary = data.notify_summary
    current_company.notify_security = data.notify_security
    db.commit()
    return {"message": "Preferences saved."}

# 6. PUBLIC ENDPOINT TO SERVE COMPANY LOGO BY ID (FIXED RETURN)
@router.get("/public/logo/{company_id}")
def get_public_logo(company_id: int, db: Session = Depends(get_db)):
    company = db.query(models.Company).filter(models.Company.id == company_id).first()
    
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found.")
        
    if not company.logo:
        # Return a true 404/400 error if image data is missing
        # This is better than returning a blank 200 OK
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Logo not uploaded.")

    # Check if the image is a JPEG (most common) or PNG
    # Assuming most logos are uploaded as PNGs
    media_type = "image/png"
    if company.logo[:3] == b'\xff\xd8\xff': # Check for JPEG magic number
        media_type = "image/jpeg"

    return StreamingResponse(io.BytesIO(company.logo), media_type=media_type)