import sys
import os
sys.path.append(os.getcwd())

from fastapi.testclient import TestClient
from app.web.app import app
from app.database import SessionLocal
from app.models.user import User
from app.services.auth.user_service import create_user

def debug_login():
    db = SessionLocal()
    try:
        # Check if any user exists
        user = db.query(User).first()
        if not user:
            print("No users found. Creating 'admin' user...")
            create_user(db, "admin", "admin@example.com", "admin123")
            print("Created user 'admin' with password 'admin123'")
        else:
            print(f"Found user: {user.username}")
    except Exception as e:
        print(f"Database error: {e}")
        return
    finally:
        db.close()

    client = TestClient(app)
    
    print("\n--- Testing Login with Invalid Credentials ---")
    try:
        response = client.post(
            "/auth/login",
            data={"username": "admin", "password": "wrongpassword"},
            allow_redirects=False
        )
        print(f"Status Code: {response.status_code}")
        if response.status_code == 500:
             print("Hit 500 Error!")
             print(response.text)
    except Exception as e:
        print(f"Exception during invalid login: {e}")

    print("\n--- Testing Login with Valid Credentials ---")
    try:
        response = client.post(
            "/auth/login",
            data={"username": "admin", "password": "admin123"},
            allow_redirects=False
        )
        print(f"Status Code: {response.status_code}")
        if response.status_code == 500:
             print("Hit 500 Error!")
             print(response.text)
    except Exception as e:
        print(f"Exception during valid login: {e}")

if __name__ == "__main__":
    debug_login()
