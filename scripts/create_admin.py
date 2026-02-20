#!/usr/bin/env python
"""
Create Admin User Script

This script creates an initial admin user for the EASM platform.

Usage:
    python scripts/create_admin.py

The script will prompt for user details interactively.
"""

import sys
import os
from pathlib import Path
from getpass import getpass

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.orm import Session
from app.database import SessionLocal, engine
from app.models.auth import User, TenantMembership
from app.models.database import Tenant, Base


def create_admin_user(
    email: str,
    username: str,
    password: str,
    full_name: str = None,
    tenant_name: str = "Default Tenant",
    tenant_slug: str = "default"
):
    """
    Create admin user and default tenant

    Args:
        email: User email
        username: Username
        password: Password (will be hashed)
        full_name: Optional full name
        tenant_name: Name of default tenant
        tenant_slug: Slug of default tenant
    """
    db = SessionLocal()

    try:
        # Check if user already exists
        existing_user = db.query(User).filter(
            (User.email == email) | (User.username == username)
        ).first()

        if existing_user:
            print(f"\nError: User with email '{email}' or username '{username}' already exists")
            return False

        # Create or get default tenant
        tenant = db.query(Tenant).filter(Tenant.slug == tenant_slug).first()

        if not tenant:
            print(f"\nCreating tenant: {tenant_name}")
            tenant = Tenant(
                name=tenant_name,
                slug=tenant_slug,
                contact_policy="admin@example.com"
            )
            db.add(tenant)
            db.flush()  # Get tenant ID
            print(f"  ✓ Tenant created (ID: {tenant.id})")
        else:
            print(f"\nUsing existing tenant: {tenant_name} (ID: {tenant.id})")

        # Create admin user
        print(f"\nCreating admin user: {username}")
        user = User(
            email=email,
            username=username,
            hashed_password=User.hash_password(password),
            full_name=full_name,
            is_superuser=True,
            is_active=True
        )
        db.add(user)
        db.flush()  # Get user ID
        print(f"  ✓ User created (ID: {user.id})")

        # Create tenant membership
        print(f"\nCreating tenant membership")
        membership = TenantMembership(
            user_id=user.id,
            tenant_id=tenant.id,
            role="admin",
            is_active=True
        )
        db.add(membership)

        # Commit all changes
        db.commit()
        print(f"  ✓ Tenant membership created")

        print("\n" + "="*60)
        print("SUCCESS: Admin user created successfully!")
        print("="*60)
        print(f"\nUser Details:")
        print(f"  Email:     {email}")
        print(f"  Username:  {username}")
        print(f"  Full Name: {full_name or 'Not set'}")
        print(f"  Role:      Admin (Superuser)")
        print(f"\nTenant:")
        print(f"  Name: {tenant.name}")
        print(f"  Slug: {tenant.slug}")
        print(f"\nYou can now login at: http://localhost:8000/api/docs")
        print("")

        return True

    except Exception as e:
        db.rollback()
        print(f"\nError creating admin user: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        db.close()


def prompt_user_details():
    """
    Interactively prompt for user details

    Returns:
        Dict with user details
    """
    print("="*60)
    print("EASM Platform - Create Admin User")
    print("="*60)
    print("")

    # Email
    while True:
        email = input("Email address: ").strip()
        if '@' in email and '.' in email:
            break
        print("  Error: Invalid email address")

    # Username
    while True:
        username = input("Username: ").strip()
        if len(username) >= 3:
            break
        print("  Error: Username must be at least 3 characters")

    # Full name (optional)
    full_name = input("Full name (optional): ").strip()
    if not full_name:
        full_name = None

    # Password
    while True:
        password = getpass("Password (min 8 chars): ")
        if len(password) < 8:
            print("  Error: Password must be at least 8 characters")
            continue

        password_confirm = getpass("Confirm password: ")
        if password != password_confirm:
            print("  Error: Passwords do not match")
            continue

        break

    # Tenant details
    print("\nDefault tenant details:")
    tenant_name = input("Tenant name (default: Default Tenant): ").strip()
    if not tenant_name:
        tenant_name = "Default Tenant"

    tenant_slug = input("Tenant slug (default: default): ").strip()
    if not tenant_slug:
        tenant_slug = "default"

    return {
        'email': email,
        'username': username,
        'password': password,
        'full_name': full_name,
        'tenant_name': tenant_name,
        'tenant_slug': tenant_slug
    }


def main():
    """Main entry point"""
    # Check database connection
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("✓ Database connection OK\n")
    except Exception as e:
        print(f"Error: Cannot connect to database: {e}")
        print("\nMake sure:")
        print("  1. PostgreSQL is running")
        print("  2. Database credentials are correct in .env")
        print("  3. Database migrations have been run (alembic upgrade head)")
        sys.exit(1)

    # Ensure tables exist
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"Error creating tables: {e}")
        sys.exit(1)

    # Get user details
    user_details = prompt_user_details()

    # Confirm
    print("\n" + "="*60)
    print("Creating admin user with the following details:")
    print("="*60)
    print(f"  Email:     {user_details['email']}")
    print(f"  Username:  {user_details['username']}")
    print(f"  Full Name: {user_details['full_name'] or 'Not set'}")
    print(f"  Tenant:    {user_details['tenant_name']} ({user_details['tenant_slug']})")
    print("")

    confirm = input("Proceed? [y/N]: ").strip().lower()
    if confirm != 'y':
        print("Cancelled")
        sys.exit(0)

    # Create user
    success = create_admin_user(**user_details)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
