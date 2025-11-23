"""Database configuration and session management."""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Get database path from environment or use default
DB_PATH = os.getenv("DB_PATH", "isir_watcher.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

# Create engine
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # Needed for SQLite
    echo=False  # Set to True for SQL query logging
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables."""
    from src.models import (
        WatchedEntity, 
        BeforeBankruptcyDocument, 
        AfterBankruptcyDocument, 
        OtherDocument,
        ApplicationDocument, 
        DisputeDocument
    )  # Import models to register them
    Base.metadata.create_all(bind=engine)

