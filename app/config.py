"""
Centralized configuration management using Pydantic Settings

All configuration values are loaded from environment variables with
sensible defaults for development. Production deployments MUST override
sensitive defaults.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator
from typing import Optional
from pathlib import Path


class Settings(BaseSettings):
    """Application settings with environment variable support"""

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore'
    )

    # Application
    app_name: str = "EASM Platform"
    app_version: str = "1.0.0"
    debug: bool = False
    environment: str = "development"

    # API Server
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 4
    api_reload: bool = False

    # Security
    secret_key: str = "CHANGE_THIS_IN_PRODUCTION"  # MUST be overridden in production
    api_key_header: str = "X-API-Key"
    cors_origins: list[str] = ["http://localhost:3000"]
    cors_allow_credentials: bool = True
    cors_allow_methods: list[str] = ["GET", "POST", "PUT", "DELETE", "PATCH"]
    cors_allow_headers: list[str] = ["*"]

    # JWT Authentication
    jwt_secret_key: str = "CHANGE_THIS_JWT_SECRET_IN_PRODUCTION"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    # Database
    postgres_host: str = "localhost"
    postgres_port: int = 15432
    postgres_db: str = "easm"
    postgres_user: str = "easm"
    postgres_password: str = "easm_dev_password"
    postgres_pool_size: int = 20
    postgres_max_overflow: int = 40
    postgres_pool_pre_ping: bool = True
    postgres_pool_recycle: int = 3600

    @property
    def database_url(self) -> str:
        """Construct PostgreSQL connection URL"""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def async_database_url(self) -> str:
        """Construct async PostgreSQL connection URL"""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 16379
    redis_db: int = 0
    redis_password: Optional[str] = None

    @property
    def redis_url(self) -> str:
        """Construct Redis connection URL"""
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    # Celery
    celery_broker_url: Optional[str] = None
    celery_result_backend: Optional[str] = None
    celery_task_always_eager: bool = False
    celery_worker_prefetch_multiplier: int = 4
    celery_worker_max_tasks_per_child: int = 1000

    @property
    def celery_broker(self) -> str:
        """Get Celery broker URL"""
        return self.celery_broker_url or self.redis_url

    @property
    def celery_backend(self) -> str:
        """Get Celery result backend URL"""
        return self.celery_result_backend or self.redis_url

    # MinIO / S3
    minio_endpoint: str = "localhost:19000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_secure: bool = False
    minio_bucket_prefix: str = "easm"

    # Tool Execution Security
    tool_execution_timeout: int = 600
    tool_execution_max_output_size: int = 100 * 1024 * 1024  # 100MB
    tool_temp_dir: Optional[Path] = None
    tool_allowed_tools: set[str] = {
        'subfinder', 'dnsx', 'httpx', 'naabu',
        'katana', 'nuclei', 'tlsx', 'uncover', 'notify'
    }

    # Discovery Pipeline
    discovery_batch_size: int = 100
    discovery_subfinder_timeout: int = 600
    discovery_amass_timeout: int = 900  # Amass is slower, needs more time
    discovery_amass_enabled: bool = True  # Enable/disable Amass enumeration
    discovery_dnsx_timeout: int = 600
    discovery_httpx_timeout: int = 900
    discovery_naabu_timeout: int = 1200
    discovery_nuclei_timeout: int = 1800

    # Rate Limiting
    rate_limit_enabled: bool = True
    rate_limit_requests_per_minute: int = 60
    rate_limit_requests_per_hour: int = 1000

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"  # json or text
    log_file: Optional[Path] = None
    log_rotation_size: str = "100MB"
    log_retention_days: int = 30

    # Monitoring
    sentry_dsn: Optional[str] = None
    sentry_environment: Optional[str] = None
    sentry_traces_sample_rate: float = 0.1

    # Feature Flags
    feature_uncover_enabled: bool = True
    feature_nuclei_enabled: bool = True
    feature_notifications_enabled: bool = False

    @model_validator(mode='after')
    def validate_production_secrets(self):
        """
        Validate that production secrets have been changed from defaults

        Raises:
            ValueError: If production environment has weak/default secrets
        """
        if self.environment == 'production':
            errors = []

            # Check SECRET_KEY
            if 'CHANGE_THIS' in self.secret_key or len(self.secret_key) < 32:
                errors.append(
                    "SECRET_KEY must be set with a strong random value (min 32 chars) in production. "
                    "Generate with: python -c \"import secrets; print(secrets.token_urlsafe(64))\""
                )

            # Check JWT_SECRET_KEY
            if 'CHANGE_THIS' in self.jwt_secret_key or len(self.jwt_secret_key) < 32:
                errors.append(
                    "JWT_SECRET_KEY must be set with a strong random value (min 32 chars) in production. "
                    "Generate with: python -c \"import secrets; print(secrets.token_urlsafe(64))\""
                )

            # Check database password
            if self.postgres_password in ['easm_dev_password', 'password', '123456', 'admin']:
                errors.append(
                    "POSTGRES_PASSWORD must be set with a strong password in production"
                )

            # Check MinIO credentials
            if self.minio_access_key == 'minioadmin' or self.minio_secret_key == 'minioadmin':
                errors.append(
                    "MINIO_ACCESS_KEY and MINIO_SECRET_KEY must be changed from defaults in production"
                )

            # Check CORS configuration
            if "*" in self.cors_origins:
                errors.append(
                    "CORS_ORIGINS must not include wildcard ('*') in production. "
                    "Specify exact allowed origins."
                )

            if errors:
                error_msg = "\n\n" + "="*80 + "\n"
                error_msg += "PRODUCTION CONFIGURATION ERRORS DETECTED\n"
                error_msg += "="*80 + "\n\n"
                error_msg += "The following configuration issues MUST be fixed before deploying to production:\n\n"
                for i, error in enumerate(errors, 1):
                    error_msg += f"{i}. {error}\n\n"
                error_msg += "="*80 + "\n"
                error_msg += "Set ENVIRONMENT=development to bypass these checks for local development.\n"
                error_msg += "="*80 + "\n"
                raise ValueError(error_msg)

        return self


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """
    Get settings instance for dependency injection

    Returns:
        Settings instance
    """
    return settings
