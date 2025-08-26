"""
Secure secret management utilities

Provides centralized secret management with support for multiple backends
and automatic rotation capabilities.
"""

import os
import secrets
from typing import Optional, Dict, Any
from pathlib import Path
import logging
import json
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2

logger = logging.getLogger(__name__)


class SecretManager:
    """
    Centralized secret management with multiple backend support

    Features:
    - Environment variable backend (default)
    - File-based encrypted storage
    - Secret rotation
    - Audit logging
    """

    def __init__(self, backend: str = 'env', key_file: Optional[Path] = None):
        """
        Initialize secret manager with specified backend

        Args:
            backend: Secret storage backend ('env', 'file', 'vault', 'azure', 'aws')
            key_file: Path to encryption key file (for file backend)
        """
        self.backend = backend
        self.key_file = key_file
        self._cache: Dict[str, str] = {}
        self._fernet: Optional[Fernet] = None

        if backend == 'file':
            self._initialize_file_backend()

    def _initialize_file_backend(self):
        """Initialize file-based encrypted secret storage"""
        if not self.key_file:
            self.key_file = Path.home() / '.easm' / 'secret.key'

        # Create directory if it doesn't exist
        self.key_file.parent.mkdir(parents=True, exist_ok=True)

        # Generate or load encryption key
        if self.key_file.exists():
            with open(self.key_file, 'rb') as f:
                key = f.read()
        else:
            key = Fernet.generate_key()
            with open(self.key_file, 'wb') as f:
                f.write(key)
            # Set restrictive permissions
            os.chmod(self.key_file, 0o600)

        self._fernet = Fernet(key)

    def get_secret(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        Retrieve secret from backend

        Args:
            key: Secret key
            default: Default value if not found

        Returns:
            Secret value or default
        """
        # Check cache first
        if key in self._cache:
            return self._cache[key]

        try:
            if self.backend == 'env':
                value = os.getenv(key, default)

                # Check for unsafe defaults
                if value and any(unsafe in value for unsafe in ['CHANGE_THIS', 'changeme', 'password123']):
                    logger.warning(f"Secret {key} contains unsafe default value")
                    if os.getenv('ENVIRONMENT') == 'production':
                        raise ValueError(f"Secret {key} has not been properly configured for production")

                self._cache[key] = value
                return value

            elif self.backend == 'file':
                return self._get_from_file(key, default)

            # Placeholder for other backends
            # elif self.backend == 'vault':
            #     return self._get_from_vault(key, default)
            # elif self.backend == 'azure':
            #     return self._get_from_azure(key, default)
            # elif self.backend == 'aws':
            #     return self._get_from_aws(key, default)

            else:
                logger.warning(f"Unknown backend: {self.backend}, falling back to env")
                return os.getenv(key, default)

        except Exception as e:
            logger.error(f"Failed to retrieve secret {key}: {e}")
            if default is not None:
                return default
            raise

    def _get_from_file(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get secret from encrypted file storage"""
        secrets_file = self.key_file.parent / 'secrets.enc'

        if not secrets_file.exists():
            return default

        try:
            with open(secrets_file, 'rb') as f:
                encrypted_data = f.read()

            decrypted_data = self._fernet.decrypt(encrypted_data)
            secrets_dict = json.loads(decrypted_data.decode())

            value = secrets_dict.get(key, default)
            if value:
                self._cache[key] = value
            return value

        except Exception as e:
            logger.error(f"Failed to read secret from file: {e}")
            return default

    def set_secret(self, key: str, value: str):
        """
        Store a secret

        Args:
            key: Secret key
            value: Secret value
        """
        if self.backend == 'env':
            os.environ[key] = value
            self._cache[key] = value

        elif self.backend == 'file':
            self._set_to_file(key, value)

        # Log audit event (without the actual secret)
        logger.info(f"Secret {key} was updated at {datetime.utcnow().isoformat()}")

    def _set_to_file(self, key: str, value: str):
        """Store secret in encrypted file"""
        secrets_file = self.key_file.parent / 'secrets.enc'

        # Load existing secrets
        if secrets_file.exists():
            with open(secrets_file, 'rb') as f:
                encrypted_data = f.read()
            decrypted_data = self._fernet.decrypt(encrypted_data)
            secrets_dict = json.loads(decrypted_data.decode())
        else:
            secrets_dict = {}

        # Update secret
        secrets_dict[key] = value
        secrets_dict[f'{key}_updated'] = datetime.utcnow().isoformat()

        # Encrypt and save
        encrypted_data = self._fernet.encrypt(json.dumps(secrets_dict).encode())
        with open(secrets_file, 'wb') as f:
            f.write(encrypted_data)

        # Set restrictive permissions
        os.chmod(secrets_file, 0o600)

        # Update cache
        self._cache[key] = value

    def generate_secure_secret(self, length: int = 64) -> str:
        """
        Generate cryptographically secure secret

        Args:
            length: Length of secret to generate

        Returns:
            Secure random string
        """
        return secrets.token_urlsafe(length)

    def rotate_secret(self, key: str) -> str:
        """
        Rotate a secret to a new value

        Args:
            key: Secret key to rotate

        Returns:
            New secret value
        """
        # Generate new secret
        new_secret = self.generate_secure_secret()

        # Store the new secret
        self.set_secret(key, new_secret)

        # Store rotation metadata
        self.set_secret(f'{key}_rotated_at', datetime.utcnow().isoformat())

        logger.info(f"Secret {key} was rotated at {datetime.utcnow().isoformat()}")

        return new_secret

    def validate_secrets(self, required_secrets: list) -> dict:
        """
        Validate that all required secrets are present and meet criteria

        Args:
            required_secrets: List of required secret keys

        Returns:
            Dict with validation results
        """
        results = {
            'valid': True,
            'missing': [],
            'weak': [],
            'errors': []
        }

        for secret_key in required_secrets:
            value = self.get_secret(secret_key)

            if not value:
                results['missing'].append(secret_key)
                results['valid'] = False
                continue

            # Check for weak secrets
            weak_patterns = [
                'password', '123456', 'admin', 'secret',
                'changeme', 'CHANGE_THIS', 'default', 'test'
            ]

            if any(pattern in value.lower() for pattern in weak_patterns):
                results['weak'].append(secret_key)
                results['valid'] = False

            # Check minimum length
            if len(value) < 16:
                results['errors'].append(f"{secret_key} is too short (minimum 16 characters)")
                results['valid'] = False

        return results

    def clear_cache(self):
        """Clear the secret cache"""
        self._cache.clear()


class SecretRotationScheduler:
    """
    Manages automatic secret rotation schedules
    """

    def __init__(self, secret_manager: SecretManager):
        """
        Initialize rotation scheduler

        Args:
            secret_manager: SecretManager instance
        """
        self.secret_manager = secret_manager
        self.rotation_schedule = {
            'jwt_secret_key': timedelta(days=30),
            'api_key': timedelta(days=90),
            'database_password': timedelta(days=60),
        }

    def check_rotation_needed(self, key: str) -> bool:
        """
        Check if a secret needs rotation

        Args:
            key: Secret key to check

        Returns:
            True if rotation is needed
        """
        if key not in self.rotation_schedule:
            return False

        # Get last rotation time
        rotated_at_key = f'{key}_rotated_at'
        rotated_at_str = self.secret_manager.get_secret(rotated_at_key)

        if not rotated_at_str:
            # Never rotated, should rotate
            return True

        try:
            rotated_at = datetime.fromisoformat(rotated_at_str)
            rotation_interval = self.rotation_schedule[key]
            next_rotation = rotated_at + rotation_interval

            return datetime.utcnow() >= next_rotation

        except (ValueError, TypeError) as e:
            logger.error(f"Failed to parse rotation timestamp for {key}: {e}")
            return True

    def rotate_if_needed(self, key: str) -> Optional[str]:
        """
        Rotate secret if needed based on schedule

        Args:
            key: Secret key to potentially rotate

        Returns:
            New secret value if rotated, None otherwise
        """
        if self.check_rotation_needed(key):
            logger.info(f"Rotating secret {key} based on schedule")
            return self.secret_manager.rotate_secret(key)
        return None

    def rotate_all_if_needed(self) -> dict:
        """
        Check and rotate all secrets based on schedule

        Returns:
            Dict of rotated secrets
        """
        rotated = {}

        for key in self.rotation_schedule:
            new_value = self.rotate_if_needed(key)
            if new_value:
                rotated[key] = "ROTATED (value hidden)"

        return rotated


def initialize_secrets(backend: str = 'env') -> SecretManager:
    """
    Initialize and validate secret manager

    Args:
        backend: Secret backend to use

    Returns:
        Configured SecretManager instance
    """
    manager = SecretManager(backend=backend)

    # Define required secrets
    required_secrets = [
        'SECRET_KEY',
        'JWT_SECRET_KEY',
        'POSTGRES_PASSWORD',
    ]

    # Validate secrets in production
    if os.getenv('ENVIRONMENT') == 'production':
        validation = manager.validate_secrets(required_secrets)

        if not validation['valid']:
            error_msg = "Secret validation failed:\n"

            if validation['missing']:
                error_msg += f"  Missing secrets: {', '.join(validation['missing'])}\n"

            if validation['weak']:
                error_msg += f"  Weak secrets: {', '.join(validation['weak'])}\n"

            if validation['errors']:
                error_msg += f"  Errors: {', '.join(validation['errors'])}\n"

            raise ValueError(error_msg)

    # Generate missing secrets in development
    else:
        for secret_key in required_secrets:
            if not manager.get_secret(secret_key):
                logger.info(f"Generating development secret for {secret_key}")
                value = manager.generate_secure_secret()
                manager.set_secret(secret_key, value)

    return manager