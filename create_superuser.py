# backend/create_superuser.py
from database import SessionLocal, engine
from models import Company, Base
from passlib.context import CryptContext

# 1. Setup Password Hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
def get_password_hash(password):
    return pwd_context.hash(password)

# 2. Create the User
def create_admin():
    db = SessionLocal()
    
    email = "samratghimire01@gmail.com"
    password = "Samrat@2003" # <--- This is your password
    
    # Check if exists
    existing = db.query(Company).filter(Company.email == email).first()
    if existing:
        print(f"User {email} already exists. Updating to Admin...")
        existing.is_admin = True
        existing.status = 'verified'
        existing.password_hash = get_password_hash(password)
    else:
        print(f"Creating new Super Admin: {email}")
        admin_user = Company(
            name="SkillSathi HQ",
            email=email,
            password_hash=get_password_hash(password),
            is_admin=True,
            status='verified',
            business_reg_number="ADMIN-001",
            primary_contact_name="System Admin",
            citizenship_number="000",
            subscription_tier="pro"
        )
        db.add(admin_user)
    
    db.commit()
    db.close()
    print("✅ Super Admin created successfully!")
    print(f"📧 Email: {email}")
    print(f"🔑 Password: {password}")

if __name__ == "__main__":
    create_admin()