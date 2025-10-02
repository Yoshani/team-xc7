"""
Database connection module for FastAPI backend
Uses SQLAlchemy to connect to MariaDB
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from tdp_secrets import DB_PASSWORD

# ==========================
# Database credentials
# ==========================
HOSTNAME = "ok913f.h.filess.io"
DATABASE = "devdb_nicealone"
PORT = "3305"
USERNAME = "devdb_nicealone"
PASSWORD = DB_PASSWORD

# ==========================
# Connection string
# ==========================
DATABASE_URL = f"mysql+pymysql://{USERNAME}:{PASSWORD}@{HOSTNAME}:{PORT}/{DATABASE}"

# Create engine
engine = create_engine(
    DATABASE_URL,
    echo=True,  # Set to False in production
    pool_pre_ping=True
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


# Dependency for FastAPI routes
def get_db():
    """
    Yield a database session for route handlers.
    Ensures session is closed after use.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
