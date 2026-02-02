import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal, init_db
from app.services.auth.user_service import create_user

def create_admin():
    """Create default admin user"""
    init_db()
    db = SessionLocal()
    
    try:
        password = os.environ.get("MINIFW_ADMIN_PASSWORD")
        if not password:
            print("❌ Error: MINIFW_ADMIN_PASSWORD environment variable is not set.")
            sys.exit(1)
            
        admin = create_user(
            db=db,
            username="admin",
            email="admin@minifw.local",
            password=password
        )
        print(f"✅ Admin user created: {admin.username}")
        print(f"   Email: {admin.email}")
        print(f"   Password: [REDACTED] (from env)")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    create_admin()
