#!/usr/bin/env python3
"""
Generate cryptographically secure secrets for production deployment

This script generates all required secrets for the EASM platform and outputs
them in a format suitable for .env files or environment variable export.

Sprint 2 Security Enhancement
"""

import secrets
import sys


def generate_secret(length: int = 64) -> str:
    """Generate a URL-safe base64-encoded secret"""
    return secrets.token_urlsafe(length)


def generate_password(length: int = 32) -> str:
    """Generate a strong alphanumeric password"""
    alphabet = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()_+-='
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def main():
    """Generate all required secrets"""
    print("=" * 80)
    print("EASM PLATFORM - PRODUCTION SECRET GENERATOR")
    print("=" * 80)
    print()
    print("Copy these values to your .env file or export as environment variables:")
    print()
    print("-" * 80)
    print()

    # Core application secrets
    print("# Core Application Secrets")
    print(f"export SECRET_KEY=\"{generate_secret(64)}\"")
    print(f"export JWT_SECRET_KEY=\"{generate_secret(64)}\"")
    print()

    # Database credentials
    print("# Database Credentials")
    print(f"export POSTGRES_PASSWORD=\"{generate_password(32)}\"")
    print()

    # Redis credentials
    print("# Redis Credentials")
    print(f"export REDIS_PASSWORD=\"{generate_password(24)}\"")
    print()

    # MinIO/S3 credentials
    print("# MinIO/S3 Credentials")
    print(f"export MINIO_ACCESS_KEY=\"{generate_password(20)}\"")
    print(f"export MINIO_SECRET_KEY=\"{generate_secret(40)}\"")
    print()

    # Production environment
    print("# Environment Configuration")
    print("export ENVIRONMENT=\"production\"")
    print()

    print("-" * 80)
    print()
    print("IMPORTANT SECURITY NOTES:")
    print()
    print("1. Store these secrets securely (password manager, vault, secrets manager)")
    print("2. Never commit these secrets to version control")
    print("3. Use different secrets for each environment (dev, staging, production)")
    print("4. Rotate secrets periodically (recommended: every 90 days)")
    print("5. Limit access to production secrets to authorized personnel only")
    print()
    print("For .env file format, remove 'export ' prefix:")
    print("  SECRET_KEY=\"...\"  (instead of export SECRET_KEY=\"...\")")
    print()
    print("=" * 80)
    print()


if __name__ == "__main__":
    main()
