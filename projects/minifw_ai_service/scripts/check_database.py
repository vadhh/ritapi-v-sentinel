import sys
from pathlib import Path
import sqlite3

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import DATABASE_PATH, SQLALCHEMY_DATABASE_URL

def check_database():
    """Check database file and contents"""
    print("=== Database Information ===\n")
    
    # Database path info
    print(f"📁 Database URL: {SQLALCHEMY_DATABASE_URL}")
    print(f"📁 Database Path: {DATABASE_PATH}")
    print(f"📁 Absolute Path: {DATABASE_PATH.resolve()}")
    
    # Check if file exists
    if not DATABASE_PATH.exists():
        print(f"\n❌ Database file DOES NOT EXIST!")
        return
    
    print(f"✅ Database file exists")
    
    # File info
    import os
    stat = os.stat(DATABASE_PATH)
    print(f"📊 File size: {stat.st_size:,} bytes")
    from datetime import datetime
    print(f"📅 Last modified: {datetime.fromtimestamp(stat.st_mtime)}")
    
    # Check users in database
    print("\n" + "="*60)
    print("👥 Users in database:\n")
    
    try:
        conn = sqlite3.connect(str(DATABASE_PATH))
        cursor = conn.cursor()
        
        # Check if users table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users';")
        if not cursor.fetchone():
            print("❌ Table 'users' does not exist!")
            
            # Show all tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            print("\nAvailable tables:")
            for table in tables:
                print(f"  - {table[0]}")
            return
        
        # Get all users
        cursor.execute("""
            SELECT id, username, email, is_active, is_2fa_enabled, 
                   created_at, last_login 
            FROM users
        """)
        
        users = cursor.fetchall()
        
        if not users:
            print("📋 No users found in database")
        else:
            print(f"📋 Total users: {len(users)}\n")
            print(f"{'ID':<5} {'Username':<15} {'Email':<25} {'Active':<8} {'2FA':<8}")
            print("-" * 70)
            
            for user in users:
                user_id, username, email, is_active, is_2fa, created, last_login = user
                print(f"{user_id:<5} {username:<15} {email:<25} "
                      f"{'✓' if is_active else '✗':<8} "
                      f"{'✓' if is_2fa else '✗':<8}")
            
            # Show password hashes (for debugging)
            print("\n🔐 Password hashes:")
            cursor.execute("SELECT username, hashed_password FROM users")
            for username, hash in cursor.fetchall():
                print(f"  {username}: {hash[:60]}...")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error reading database: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_database()