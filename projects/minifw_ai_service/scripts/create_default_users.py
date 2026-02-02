"""
Create Default Users Script
Creates initial users for each role and sector for testing
"""

import sqlite3
from passlib.context import CryptContext
from datetime import datetime

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_default_users(db_path: str = "minifw.db"):
    """Create default users for each role"""
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Default users configuration
    default_users = [
        # Super Admin - can access everything
        {
            "username": "superadmin",
            "email": "superadmin@minifw.local",
            "password": "SuperAdmin@2026!",  # CHANGE IN PRODUCTION
            "role": "super_admin",
            "sector": "general",
            "full_name": "Super Administrator",
            "department": "IT Security"
        },
        
        # Hospital Sector Users
        {
            "username": "hospital_admin",
            "email": "admin@hospital.local",
            "password": "HospitalAdmin@2026!",
            "role": "admin",
            "sector": "hospital",
            "full_name": "Hospital Administrator",
            "department": "IT Department"
        },
        {
            "username": "hospital_operator",
            "email": "operator@hospital.local",
            "password": "HospitalOp@2026!",
            "role": "operator",
            "sector": "hospital",
            "full_name": "Hospital Security Operator",
            "department": "Security Operations"
        },
        {
            "username": "hospital_auditor",
            "email": "auditor@hospital.local",
            "password": "HospitalAudit@2026!",
            "role": "auditor",
            "sector": "hospital",
            "full_name": "Hospital Compliance Auditor",
            "department": "Compliance"
        },
        
        # School Sector Users
        {
            "username": "school_admin",
            "email": "admin@school.local",
            "password": "SchoolAdmin@2026!",
            "role": "admin",
            "sector": "school",
            "full_name": "School IT Administrator",
            "department": "IT Department"
        },
        {
            "username": "school_operator",
            "email": "operator@school.local",
            "password": "SchoolOp@2026!",
            "role": "operator",
            "sector": "school",
            "full_name": "School Security Operator",
            "department": "IT Security"
        },
        {
            "username": "school_auditor",
            "email": "auditor@school.local",
            "password": "SchoolAudit@2026!",
            "role": "auditor",
            "sector": "school",
            "full_name": "School Safety Officer",
            "department": "Student Safety"
        },
        
        # Government Sector Users
        {
            "username": "gov_admin",
            "email": "admin@government.local",
            "password": "GovAdmin@2026!",
            "role": "admin",
            "sector": "government",
            "full_name": "Government IT Administrator",
            "department": "Cybersecurity Division"
        },
        {
            "username": "gov_operator",
            "email": "operator@government.local",
            "password": "GovOp@2026!",
            "role": "operator",
            "sector": "government",
            "full_name": "Government Security Operator",
            "department": "SOC Team"
        },
        {
            "username": "gov_auditor",
            "email": "auditor@government.local",
            "password": "GovAudit@2026!",
            "role": "auditor",
            "sector": "government",
            "full_name": "Government Compliance Officer",
            "department": "Internal Audit"
        },
        
        # Read-only viewer
        {
            "username": "viewer",
            "email": "viewer@minifw.local",
            "password": "Viewer@2026!",
            "role": "viewer",
            "sector": "general",
            "full_name": "Read Only Viewer",
            "department": "Monitoring"
        }
    ]
    
    try:
        print("\n=== Creating Default Users ===\n")
        
        created_count = 0
        skipped_count = 0
        
        for user_data in default_users:
            # Check if user already exists
            cursor.execute(
                "SELECT id FROM users WHERE username = ? OR email = ?",
                (user_data["username"], user_data["email"])
            )
            
            if cursor.fetchone():
                print(f"⊙ User {user_data['username']} already exists, skipping")
                skipped_count += 1
                continue
            
            # Hash password
            hashed_password = pwd_context.hash(user_data["password"])
            
            # Insert user
            cursor.execute("""
                INSERT INTO users (
                    username, email, hashed_password, role, sector,
                    full_name, department, is_active, must_change_password,
                    created_at, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, 1, ?, 'system')
            """, (
                user_data["username"],
                user_data["email"],
                hashed_password,
                user_data["role"],
                user_data["sector"],
                user_data["full_name"],
                user_data["department"],
                datetime.utcnow().isoformat()
            ))
            
            print(f"✓ Created user: {user_data['username']} ({user_data['role']} - {user_data['sector']})")
            created_count += 1
            
            # Log user creation in audit log
            cursor.execute("""
                INSERT INTO audit_logs (
                    action, description, username, severity,
                    resource_type, resource_id, after_value
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                'user_created',
                f"Default user {user_data['username']} created during setup",
                'system',
                'info',
                'user',
                user_data['username'],
                f'{{"role": "{user_data["role"]}", "sector": "{user_data["sector"]}"}}'
            ))
        
        conn.commit()
        
        print(f"\n=== User Creation Summary ===")
        print(f"Created: {created_count} users")
        print(f"Skipped: {skipped_count} users (already exist)")
        
        if created_count > 0:
            print("\n⚠️  IMPORTANT: Default passwords must be changed on first login!")
            print("\nDefault Credentials:")
            print("-" * 70)
            for user in default_users:
                print(f"Username: {user['username']:20} Password: {user['password']}")
            print("-" * 70)
            print("\n⚠️  STORE THESE CREDENTIALS SECURELY AND CHANGE THEM IMMEDIATELY!")
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Error creating users: {str(e)}")
        raise
    
    finally:
        conn.close()


def show_users(db_path: str = "minifw.db"):
    """Display all users in the database"""
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT username, email, role, sector, is_active, created_at, last_login
        FROM users
        ORDER BY role, sector, username
    """)
    
    users = cursor.fetchall()
    
    print("\n=== Current Users ===\n")
    print(f"{'Username':<20} {'Role':<15} {'Sector':<12} {'Active':<8} {'Last Login':<20}")
    print("-" * 95)
    
    for user in users:
        username, email, role, sector, is_active, created_at, last_login = user
        active_str = "Yes" if is_active else "No"
        last_login_str = last_login[:19] if last_login else "Never"
        
        print(f"{username:<20} {role:<15} {sector:<12} {active_str:<8} {last_login_str:<20}")
    
    print(f"\nTotal users: {len(users)}\n")
    
    conn.close()


if __name__ == "__main__":
    import sys
    
    print("╔═══════════════════════════════════════════════════════════╗")
    print("║   MiniFW-AI V-Sentinel User Setup Tool                  ║")
    print("║   Create Default Users for RBAC Testing                  ║")
    print("╚═══════════════════════════════════════════════════════════╝\n")
    
    db_path = sys.argv[1] if len(sys.argv) > 1 else "minifw.db"
    
    if "--show" in sys.argv:
        show_users(db_path)
    else:
        response = input("Create default users? (yes/no): ")
        
        if response.lower() in ['yes', 'y']:
            create_default_users(db_path)
            print("\nShowing created users:")
            show_users(db_path)
        else:
            print("User creation cancelled.")