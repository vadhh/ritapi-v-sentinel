"""
Database Migration Script for MiniFW-AI_Sectors V-Sentinel
Upgrades existing database to support RBAC and audit logging
FIXED: Uses timezone-aware datetime
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def migrate_database(db_path: str = "minifw.db"):
    """
    Migrate existing database to new schema with RBAC and audit logging
    
    BACKUP IS CREATED AUTOMATICALLY BEFORE MIGRATION
    """
    
    db_file = Path(db_path)
    
    if not db_file.exists():
        print(f"Database {db_path} not found. Creating new database...")
        create_new_database(db_path)
        return
    
    # Create backup
    backup_path = f"{db_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    print(f"Creating backup: {backup_path}")
    
    import shutil
    shutil.copy2(db_path, backup_path)
    print("✓ Backup created successfully")
    
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        print("\n=== Starting Database Migration ===\n")
        
        # 1. Add new columns to users table
        print("1. Upgrading users table...")
        
        now_iso = datetime.now(timezone.utc).isoformat()
        
        new_columns = [
            ("role", "VARCHAR(20)", "viewer"),
            ("sector", "VARCHAR(20)", "general"),
            ("is_locked", "BOOLEAN", "0"),
            ("failed_login_attempts", "INTEGER", "0"),
            ("locked_until", "DATETIME", "NULL"),
            ("backup_codes", "VARCHAR(500)", "NULL"),
            ("session_token", "VARCHAR(255)", "NULL"),
            ("last_password_change", "DATETIME", f"'{now_iso}'"),
            ("password_expires_at", "DATETIME", "NULL"),
            ("must_change_password", "BOOLEAN", "0"),
            ("created_by", "VARCHAR(50)", "NULL"),
            ("updated_at", "DATETIME", f"'{now_iso}'"),
            ("updated_by", "VARCHAR(50)", "NULL"),
            ("last_login_ip", "VARCHAR(45)", "NULL"),
            ("full_name", "VARCHAR(100)", "NULL"),
            ("department", "VARCHAR(100)", "NULL"),
            ("phone", "VARCHAR(20)", "NULL")
        ]
        
        for column_name, column_type, default_value in new_columns:
            try:
                if default_value == "NULL":
                    cursor.execute(f"ALTER TABLE users ADD COLUMN {column_name} {column_type}")
                else:
                    cursor.execute(f"ALTER TABLE users ADD COLUMN {column_name} {column_type} DEFAULT {default_value}")
                print(f"  ✓ Added column: {column_name}")
            except sqlite3.OperationalError as e:
                if "duplicate column name" in str(e):
                    print(f"  ⊙ Column {column_name} already exists, skipping")
                else:
                    raise
        
        # Update existing users to have super_admin role
        cursor.execute("UPDATE users SET role = 'super_admin' WHERE role IS NULL OR role = 'viewer'")
        print(f"  ✓ Updated {cursor.rowcount} existing users to super_admin role")
        
        # 2. Create audit_logs table
        print("\n2. Creating audit_logs table...")
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                user_id INTEGER,
                username VARCHAR(50),
                user_role VARCHAR(20),
                user_sector VARCHAR(20),
                action VARCHAR(50) NOT NULL,
                severity VARCHAR(20) DEFAULT 'info',
                resource_type VARCHAR(50),
                resource_id VARCHAR(100),
                description TEXT NOT NULL,
                before_value JSON,
                after_value JSON,
                metadata JSON,
                ip_address VARCHAR(45),
                user_agent VARCHAR(255),
                session_id VARCHAR(255),
                success VARCHAR(10) DEFAULT 'success',
                error_message TEXT,
                compliance_flag VARCHAR(50),
                retention_until DATETIME
            )
        """)
        print("  ✓ audit_logs table created")
        
        # Create indexes for audit_logs
        print("  Creating indexes for audit_logs...")
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_logs(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_audit_user_id ON audit_logs(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_audit_username ON audit_logs(username)",
            "CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_logs(action)",
            "CREATE INDEX IF NOT EXISTS idx_audit_resource_type ON audit_logs(resource_type)",
            "CREATE INDEX IF NOT EXISTS idx_audit_resource_id ON audit_logs(resource_id)",
            "CREATE INDEX IF NOT EXISTS idx_audit_ip_address ON audit_logs(ip_address)",
            "CREATE INDEX IF NOT EXISTS idx_audit_session_id ON audit_logs(session_id)"
        ]
        
        for index_sql in indexes:
            cursor.execute(index_sql)
        print("  ✓ Indexes created")
        
        # 3. Create policy_versions table
        print("\n3. Creating policy_versions table...")
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS policy_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version_number INTEGER NOT NULL,
                sector VARCHAR(20) NOT NULL,
                policy_json JSON NOT NULL,
                checksum VARCHAR(64) NOT NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                created_by VARCHAR(50) NOT NULL,
                change_description TEXT,
                is_active BOOLEAN DEFAULT 0,
                validation_status VARCHAR(20) DEFAULT 'pending',
                deployed_at DATETIME,
                rolled_back_at DATETIME,
                rolled_back_by VARCHAR(50),
                rollback_reason TEXT
            )
        """)
        print("  ✓ policy_versions table created")
        
        # Create indexes for policy_versions
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_policy_version ON policy_versions(version_number)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_policy_sector ON policy_versions(sector)")
        print("  ✓ Indexes created")
        
        # 4. Log migration in audit log
        print("\n4. Recording migration in audit log...")
        
        cursor.execute("""
            INSERT INTO audit_logs (
                action, description, severity, username,
                resource_type, success
            ) VALUES (
                'system_migration',
                'Database migrated to support RBAC and audit logging',
                'info',
                'system',
                'database',
                'success'
            )
        """)
        print("  ✓ Migration recorded in audit log")
        
        # Commit all changes
        conn.commit()
        
        print("\n=== Migration Completed Successfully ===")
        print(f"Backup saved to: {backup_path}")
        print("\nNext steps:")
        print("1. Review the migration results")
        print("2. Update your application code to use new models")
        print("3. Create additional user accounts with appropriate roles")
        print("4. Configure sector-specific policies")
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Migration failed: {str(e)}")
        print(f"Database rolled back. Backup available at: {backup_path}")
        raise
    
    finally:
        conn.close()


def create_new_database(db_path: str = "minifw.db"):
    """Create a new database with full schema"""
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        print("Creating new database with full schema...")
        
        # Create users table
        cursor.execute("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username VARCHAR(50) UNIQUE NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                hashed_password VARCHAR(255) NOT NULL,
                role VARCHAR(20) NOT NULL DEFAULT 'viewer',
                sector VARCHAR(20) NOT NULL DEFAULT 'general',
                is_active BOOLEAN DEFAULT 1,
                is_locked BOOLEAN DEFAULT 0,
                failed_login_attempts INTEGER DEFAULT 0,
                locked_until DATETIME,
                is_2fa_enabled BOOLEAN DEFAULT 0,
                totp_secret VARCHAR(32),
                backup_codes VARCHAR(500),
                session_token VARCHAR(255),
                last_password_change DATETIME DEFAULT CURRENT_TIMESTAMP,
                password_expires_at DATETIME,
                must_change_password BOOLEAN DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                created_by VARCHAR(50),
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_by VARCHAR(50),
                last_login DATETIME,
                last_login_ip VARCHAR(45),
                full_name VARCHAR(100),
                department VARCHAR(100),
                phone VARCHAR(20)
            )
        """)
        
        # Create audit_logs table (same as migration)
        cursor.execute("""
            CREATE TABLE audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                user_id INTEGER,
                username VARCHAR(50),
                user_role VARCHAR(20),
                user_sector VARCHAR(20),
                action VARCHAR(50) NOT NULL,
                severity VARCHAR(20) DEFAULT 'info',
                resource_type VARCHAR(50),
                resource_id VARCHAR(100),
                description TEXT NOT NULL,
                before_value JSON,
                after_value JSON,
                metadata JSON,
                ip_address VARCHAR(45),
                user_agent VARCHAR(255),
                session_id VARCHAR(255),
                success VARCHAR(10) DEFAULT 'success',
                error_message TEXT,
                compliance_flag VARCHAR(50),
                retention_until DATETIME
            )
        """)
        
        # Create policy_versions table (same as migration)
        cursor.execute("""
            CREATE TABLE policy_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version_number INTEGER NOT NULL,
                sector VARCHAR(20) NOT NULL,
                policy_json JSON NOT NULL,
                checksum VARCHAR(64) NOT NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                created_by VARCHAR(50) NOT NULL,
                change_description TEXT,
                is_active BOOLEAN DEFAULT 0,
                validation_status VARCHAR(20) DEFAULT 'pending',
                deployed_at DATETIME,
                rolled_back_at DATETIME,
                rolled_back_by VARCHAR(50),
                rollback_reason TEXT
            )
        """)
        
        # Create all indexes
        indexes = [
            "CREATE INDEX idx_audit_timestamp ON audit_logs(timestamp)",
            "CREATE INDEX idx_audit_user_id ON audit_logs(user_id)",
            "CREATE INDEX idx_audit_username ON audit_logs(username)",
            "CREATE INDEX idx_audit_action ON audit_logs(action)",
            "CREATE INDEX idx_audit_resource_type ON audit_logs(resource_type)",
            "CREATE INDEX idx_audit_resource_id ON audit_logs(resource_id)",
            "CREATE INDEX idx_policy_version ON policy_versions(version_number)",
            "CREATE INDEX idx_policy_sector ON policy_versions(sector)"
        ]
        
        for index_sql in indexes:
            cursor.execute(index_sql)
        
        conn.commit()
        print("✓ New database created successfully")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Failed to create database: {str(e)}")
        raise
    
    finally:
        conn.close()


if __name__ == "__main__":
    import sys
    
    db_path = sys.argv[1] if len(sys.argv) > 1 else "minifw.db"
    
    print("╔═══════════════════════════════════════════════════════════╗")
    print("║   MiniFW-AI V-Sentinel Database Migration Tool          ║")
    print("║   RBAC + Audit Logging Implementation                    ║")
    print("╚═══════════════════════════════════════════════════════════╝\n")
    
    response = input(f"Migrate database at '{db_path}'? (yes/no): ")
    
    if response.lower() in ['yes', 'y']:
        migrate_database(db_path)
    else:
        print("Migration cancelled.")