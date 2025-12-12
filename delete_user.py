# backend/fix_enum.py
from sqlalchemy import text
from database import engine

def fix_enum():
    with engine.connect() as conn:
        print("🔧 Updating Certificate Status Enum...")
        try:
            # This raw SQL forces MySQL to accept the new value
            conn.execute(text("ALTER TABLE certificates MODIFY COLUMN status ENUM('active', 'revoked', 'expired', 'pending_approval') DEFAULT 'pending_approval'"))
            conn.commit()
            print("✅ Success: Database Enum updated.")
        except Exception as e:
            print(f"⚠️ Error: {e}")

if __name__ == "__main__":
    fix_enum()