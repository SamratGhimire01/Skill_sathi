# backend/fix_admin.py
from sqlalchemy import text
from database import engine

def make_admin():
    target_email = "samratghimire01@gmail.com"
    
    with engine.connect() as conn:
        try:
            # 1. Ensure column exists (just in case)
            try:
                conn.execute(text("ALTER TABLE companies ADD COLUMN is_admin BOOLEAN DEFAULT 0"))
            except:
                pass 

            # 2. Update the user
            conn.execute(text(f"UPDATE companies SET is_admin = 1, status = 'verified' WHERE email = '{target_email}'"))
            conn.commit()
            print(f"✅ Success: '{target_email}' is now a SUPER ADMIN.")
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    make_admin()