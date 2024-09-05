"""
Database connection and session management

Provides SQLAlchemy engine with optimized connection pooling
and session factory for dependency injection.
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import Pool
import logging

from app.config import settings

logger = logging.getLogger(__name__)

# Create engine with optimized connection pooling
engine = create_engine(
    settings.database_url,
    pool_pre_ping=settings.postgres_pool_pre_ping,
    pool_size=settings.postgres_pool_size,
    max_overflow=settings.postgres_max_overflow,
    pool_recycle=settings.postgres_pool_recycle,
    echo=settings.debug,  # Log SQL queries in debug mode
)


@event.listens_for(Pool, "connect")
def set_postgres_pragmas(dbapi_conn, connection_record):
    """Set PostgreSQL connection parameters"""
    cursor = dbapi_conn.cursor()
    # Set statement timeout to prevent long-running queries
    cursor.execute("SET statement_timeout = 30000")  # 30 seconds
    cursor.close()


@event.listens_for(Pool, "checkout")
def receive_checkout(dbapi_conn, connection_record, connection_proxy):
    """Log connection checkout for monitoring"""
    logger.debug("Database connection checked out from pool")


# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    """
    Dependency for getting database session

    Yields:
        Database session

    Example:
        @app.get("/api/assets")
        def get_assets(db: Session = Depends(get_db)):
            return db.query(Asset).all()
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database session error: {e}")
        db.rollback()
        raise
    finally:
        db.close()
