# backend/fix_tables.py
from sqlalchemy import text
from database import engine

def fix_broken_tables():
    with engine.connect() as conn:
        print("🔧 Fixing database tables...")
        
        # 1. Drop the broken audit_logs table
        try:
            conn.execute(text("DROP TABLE IF EXISTS audit_logs"))
            print("✅ Dropped broken 'audit_logs' table.")
        except Exception as e:
            print(f"⚠️ Could not drop audit_logs: {e}")

        # 2. Drop shared_certificates if it exists (just to be safe)
        try:
            conn.execute(text("DROP TABLE IF EXISTS shared_certificates"))
            print("✅ Dropped 'shared_certificates' table.")
        except Exception as e:
            print(f"⚠️ Could not drop shared_certificates: {e}")
            
        conn.commit()
        print("🚀 Tables dropped. Restart your backend to recreate them correctly!")

if __name__ == "__main__":
    fix_broken_tables()