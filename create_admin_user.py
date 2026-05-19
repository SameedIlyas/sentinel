"""
Script to create an initial admin user for the Sentinel platform

This script should be run once after initial setup to create the first
administrator account. Subsequent users can be created through the API.

Usage:
    python create_admin_user.py
"""

import sys
import uuid
from datetime import datetime
from getpass import getpass

# Add parent directory to path to import policy_engine
sys.path.insert(0, '.')

from policy_engine.database import SessionLocal
from policy_engine.models.user import User, UserRole
from policy_engine.auth.jwt_utils import get_password_hash


def create_admin_user():
    """Create an initial admin user interactively"""
    print("=" * 80)
    print("  Sentinel AI - Create Initial Admin User")
    print("=" * 80)
    print()
    
    # Get user input
    print("Enter admin user details:")
    username = input("Username: ").strip().lower()
    
    if not username:
        print("Error: Username cannot be empty")
        return
    
    if not username.replace('_', '').replace('-', '').isalnum():
        print("Error: Username must contain only letters, numbers, underscores, and hyphens")
        return
    
    email = input("Email: ").strip().lower()
    
    if not email or '@' not in email:
        print("Error: Invalid email address")
        return
    
    full_name = input("Full Name (optional): ").strip()
    
    # Get password securely
    password = getpass("Password (min 8 characters): ")
    password_confirm = getpass("Confirm Password: ")
    
    if password != password_confirm:
        print("Error: Passwords do not match")
        return
    
    if len(password) < 8:
        print("Error: Password must be at least 8 characters")
        return
    
    # Create database session
    db = SessionLocal()
    
    try:
        # Check if username already exists
        existing_user = db.query(User).filter(User.username == username).first()
        if existing_user:
            print(f"Error: Username '{username}' already exists")
            return
        
        # Check if email already exists
        existing_email = db.query(User).filter(User.email == email).first()
        if existing_email:
            print(f"Error: Email '{email}' already exists")
            return
        
        # Create admin user
        user_id = f"user_{uuid.uuid4().hex[:16]}"
        
        admin_user = User(
            id=user_id,
            username=username,
            email=email,
            password_hash=get_password_hash(password),
            role=UserRole.ORG_ADMIN,
            full_name=full_name if full_name else None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            last_login=None,
            is_active=True
        )
        
        db.add(admin_user)
        db.commit()
        
        print()
        print("=" * 80)
        print("  [OK] Admin user created successfully!")
        print("=" * 80)
        print()
        print(f"  User ID:  {admin_user.id}")
        print(f"  Username: {admin_user.username}")
        print(f"  Email:    {admin_user.email}")
        print(f"  Role:     {admin_user.role.value}")
        print()
        print("You can now login with these credentials.")
        print()
        
    except Exception as e:
        print(f"Error creating admin user: {str(e)}")
        db.rollback()
    finally:
        db.close()


def create_default_admin():
    """Create a default admin user for testing (non-interactive)"""
    db = SessionLocal()
    
    try:
        # Check if admin already exists
        existing_admin = db.query(User).filter(User.role == UserRole.ORG_ADMIN).first()
        if existing_admin:
            print(f"Admin user already exists: {existing_admin.username}")
            return
        
        # Create default admin
        user_id = f"user_{uuid.uuid4().hex[:16]}"
        
        admin_user = User(
            id=user_id,
            username="admin",
            email="admin@sentinel.ai",
            password_hash=get_password_hash("admin123"),  # Default password
            role=UserRole.ORG_ADMIN,
            full_name="System Administrator",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            last_login=None,
            is_active=True
        )
        
        db.add(admin_user)
        db.commit()
        
        print("=" * 80)
        print("  [OK] Default admin user created!")
        print("=" * 80)
        print()
        print(f"  Username: admin")
        print(f"  Password: admin123")
        print()
        print("  WARNING: Change this password immediately!")
        print()
        
    except Exception as e:
        print(f"Error creating default admin user: {str(e)}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Create admin user for Sentinel platform")
    parser.add_argument(
        "--default",
        action="store_true",
        help="Create default admin user (username: admin, password: admin123)"
    )
    
    args = parser.parse_args()
    
    if args.default:
        create_default_admin()
    else:
        create_admin_user()
