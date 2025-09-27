from sqlalchemy import text
from db.connection import engine, SessionLocal

# Test raw connection
try:
    with engine.connect() as conn:
        result = conn.execute(text("SELECT VERSION();"))
        version = result.fetchone()[0]
        print("Database version:", version)
except Exception as e:
    print("Connection failed:", e)

# Test session
try:
    db = SessionLocal()
    result = db.execute(text("SELECT 1;"))
    print("Session test:", result.scalar())
finally:
    db.close()
