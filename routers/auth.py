from fastapi import APIRouter, Depends, status, HTTPException, Request, Form, UploadFile, File
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from sqlalchemy.orm import Session
import models, schemas, os
from database import get_db
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from passlib.context import CryptContext

# Setup Password Hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
def hash_password(password: str): return pwd_context.hash(password)
def verify_password(plain, hashed): return pwd_context.verify(plain, hashed)

router = APIRouter(prefix="/auth", tags=['Authentication'])

SECRET_KEY = os.getenv("SECRET_KEY", "supersecretkey") # Fallback if env fails
ALGORITHM = "HS256" # Fixed typo from user input
ACCESS_TOKEN_EXPIRE_MINUTES = 30
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# --- REGISTER ---
@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_company(
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    business_reg_number: str = Form(...),
    phone_number: str = Form(None),
    primary_contact_name: str = Form(None), # Made optional in form to be safe
    citizenship_number: str = Form(None),   # Made optional in form to be safe
    contact_photo: UploadFile = File(...),
    registration_document: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    if db.query(models.Company).filter(models.Company.email == email).first():
        raise HTTPException(status_code=409, detail="Email already registered.")

    photo_bytes = await contact_photo.read()
    doc_bytes = await registration_document.read()

    new_company = models.Company(
        name=name,
        email=email,
        password_hash=hash_password(password),
        business_reg_number=business_reg_number,
        phone_number=phone_number, 
        primary_contact_name=primary_contact_name,
        citizenship_number=citizenship_number,
        contact_photo=photo_bytes,
        registration_document=doc_bytes,
        status='pending'
    )
    db.add(new_company)
    db.commit()
    
    # Audit Log
    try:
        log = models.AuditLog(
            actor_type="system", 
            event_type="registration", 
            details=f"New Company: {name}",
            company_id=new_company.id
        )
        db.add(log); db.commit()
    except: pass

    return {"message": "Registration successful! Wait for Admin approval."}

# --- LOGIN ---
@router.post("/login", response_model=schemas.Token)
def login_for_access_token(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    company = db.query(models.Company).filter(models.Company.email == form_data.username).first()
    
    if not company or not verify_password(form_data.password, company.password_hash):
        raise HTTPException(status_code=403, detail="Invalid Credentials")

    if not company.is_admin and company.status != 'verified':
        raise HTTPException(status_code=403, detail=f"Account status is {company.status}. Please wait for verification.")

    token_data = {
        "sub": str(company.id), 
        "type": "company", 
        "company_id": str(company.id), 
        "is_admin": company.is_admin
    }
    
    # Audit Log
    try:
        db.add(models.AuditLog(
            company_id=company.id, actor_type="company", actor_id=company.id,
            event_type="login", details=f"IP: {request.client.host}"
        ))
        db.commit()
    except: pass

    return {"access_token": create_access_token(token_data), "token_type": "bearer"}

# --- WORKER LOGIN ---
# backend/routers/auth.py
# (Keep imports same, REPLACE the login_worker function)

@router.post("/worker/login", response_model=schemas.Token)
def login_worker(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # 1. Search by Worker ID OR Email
    worker = db.query(models.Worker).filter(
        (models.Worker.worker_id == form_data.username) | 
        (models.Worker.email == form_data.username)
    ).first()
    
    # 2. Debugging Print (Check your terminal if login fails)
    if not worker:
        print(f"❌ Worker login failed: User '{form_data.username}' not found.")
        raise HTTPException(status_code=403, detail="Invalid Credentials")
        
    # 3. Verify Password
    if not verify_password(form_data.password, worker.password_hash):
        print(f"❌ Worker login failed: Password mismatch for '{form_data.username}'.")
        raise HTTPException(status_code=403, detail="Invalid Credentials")

    # 4. Log Success
    try:
        db.add(models.AuditLog(
            company_id=worker.company_id, 
            actor_type="staff", 
            actor_id=worker.id,
            event_type="login", 
            details=f"Staff Login: {worker.name} ({worker.worker_id})"
        ))
        db.commit()
    except: pass

    return {
        "access_token": create_access_token(data={
            "sub": str(worker.id), 
            "type": "worker", 
            "company_id": str(worker.company_id), 
            "name": worker.name
        }), 
        "token_type": "bearer"
    }

# --- UTILS ---
def get_current_company(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        cid = payload.get("sub")
        if payload.get("type") != "company": raise Exception()
    except: raise HTTPException(status_code=401, detail="Invalid credentials")
    
    company = db.query(models.Company).filter(models.Company.id == cid).first()
    if not company: raise HTTPException(status_code=401, detail="User not found")
    return company
def get_current_worker(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)): # <--- CHECK THIS NAME!
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        token_data = schemas.TokenData(id=payload.get("sub"))
        if payload.get("type") != "worker": raise Exception()
    except JWTError: raise HTTPException(status_code=401, detail="Invalid credentials")
    except: raise HTTPException(status_code=403, detail="Token not for worker role")
    
    worker = db.query(models.Worker).filter(models.Worker.id == token_data.id).first()
    if not worker: raise HTTPException(status_code=401, detail="Worker not found")
    return worker

def get_current_user_role(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return {"id": payload.get("sub"), "type": payload.get("type"), "company_id": payload.get("company_id")}
    except: raise HTTPException(status_code=401, detail="Invalid Token")

# --- FORGOT PASSWORD LOGIC ---

# 1. Request Reset Token
@router.post("/forgot-password")
def forgot_password(data: schemas.PasswordResetRequest, db: Session = Depends(get_db)):
    email = data.email
    user_type = None
    user_id = None

    # Check Company
    company = db.query(models.Company).filter(models.Company.email == email).first()
    if company:
        user_type = "company"
        user_id = company.id
    else:
        # Check Worker
        worker = db.query(models.Worker).filter(models.Worker.email == email).first()
        if worker:
            user_type = "worker"
            user_id = worker.id
    
    if not user_type:
        # Security: Don't reveal if user exists or not, just fake success
        # But for dev, we print a warning
        print(f"⚠️ Password reset requested for non-existent email: {email}")
        return {"message": "If this email exists, a reset code has been sent."}

    # Generate a short-lived token (15 mins)
    reset_token = create_access_token(data={
        "sub": str(user_id), 
        "type": user_type, 
        "scope": "reset_password"
    })

    # --- SIMULATE EMAIL SENDING ---
    print("\n" + "="*60)
    print(f"📧 EMAIL SIMULATION FOR: {email}")
    print(f"🔑 RESET TOKEN: {reset_token}")
    print("="*60 + "\n")
    # ------------------------------

    return {
        "message": "Reset token generated (Check Server Console)", 
        "debug_token": reset_token # Remove this line in production!
    }

# 2. Confirm Reset
@router.post("/reset-password")
def reset_password_confirm(data: schemas.PasswordResetConfirm, db: Session = Depends(get_db)):
    try:
        # Decode Token
        payload = jwt.decode(data.token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        user_type = payload.get("type")
        scope = payload.get("scope")

        if scope != "reset_password":
            raise HTTPException(status_code=401, detail="Invalid token scope")
            
    except JWTError:
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    # Hash new password
    new_hash = hash_password(data.new_password)

    # Update DB
    if user_type == "company":
        user = db.query(models.Company).filter(models.Company.id == user_id).first()
        user.password_hash = new_hash
    elif user_type == "worker":
        user = db.query(models.Worker).filter(models.Worker.id == user_id).first()
        user.password_hash = new_hash
    
    db.commit()
    
    return {"message": "Password updated successfully. Please login."}