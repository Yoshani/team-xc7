"""
CRUD operations for DB
"""

import uuid
from typing import Optional

from sqlalchemy import Column, String, Integer, Text, DateTime, DECIMAL, ForeignKey, func
from sqlalchemy.orm import relationship, Session

from .connection import Base, engine


# ==========================
# Models
# ==========================

class CodeSnapshot(Base):
    __tablename__ = "code_snapshots"

    commit_id = Column(String(36), primary_key=True)
    project_id = Column(String(36), nullable=False)
    parent_commit_id = Column(String(36), nullable=True)
    developer_name = Column(String(100), nullable=False)
    code_text = Column(Text, nullable=False)
    language = Column(String(50), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    reviews = relationship("CodeReviewSuggestion", back_populates="snapshot")


class CodeReviewSuggestion(Base):
    __tablename__ = "code_review_suggestions"

    review_id = Column(Integer, primary_key=True, autoincrement=True)
    commit_id = Column(String(36), ForeignKey("code_snapshots.commit_id"), nullable=False)
    line_start = Column(Integer)
    line_end = Column(Integer)
    suggestion = Column(Text, nullable=False)
    severity = Column(String(50))
    created_at = Column(DateTime, server_default=func.now())

    snapshot = relationship("CodeSnapshot", back_populates="reviews")
    classifications = relationship("ReviewClassification", back_populates="review")


class ReviewClassification(Base):
    __tablename__ = "review_classifications"

    classification_id = Column(Integer, primary_key=True, autoincrement=True)
    review_id = Column(Integer, ForeignKey("code_review_suggestions.review_id"), nullable=False)
    category = Column(String(100))
    classification = Column(String(50), nullable=False)  # accepted / modified / not_handled
    recurring_issue = Column(String(255))
    confidence = Column(DECIMAL(3, 2), nullable=False, default=0.0)
    rationale = Column(Text)
    created_at = Column(DateTime, server_default=func.now())

    review = relationship("CodeReviewSuggestion", back_populates="classifications")


# ==========================
# Create tables (one-time init)
# ==========================
def init_db():
    Base.metadata.create_all(bind=engine)


# ==========================
# CRUD Operations
# ==========================

# --- Snapshots ---
def create_snapshot(db: Session, project_id: str, parent_commit_id: str,
                    developer_name: str, code_text: str, language: str) -> CodeSnapshot:
    commit_id = str(uuid.uuid4())
    snapshot = CodeSnapshot(
        commit_id=commit_id,
        project_id=project_id,
        parent_commit_id=parent_commit_id if parent_commit_id else None,
        developer_name=developer_name,
        code_text=code_text,
        language=language,
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return snapshot


def get_snapshot_by_commit(db: Session, commit_id: str):
    return db.query(CodeSnapshot).filter(CodeSnapshot.commit_id == commit_id).first()


# --- Reviews ---
def create_review(db: Session, commit_id: str, line_start: int, line_end: int,
                  suggestion: str, severity: str = None) -> CodeReviewSuggestion:
    review = CodeReviewSuggestion(
        commit_id=commit_id,
        line_start=line_start,
        line_end=line_end,
        suggestion=suggestion,
        severity=severity,
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return review


def get_reviews_for_commit(db: Session, commit_id: str):
    return db.query(CodeReviewSuggestion).filter(
        CodeReviewSuggestion.commit_id == commit_id
    ).all()


# --- Classifications ---
def create_classification(db: Session, review_id: int, category: str, classification: str, recurring_issue: str,
                          confidence: float, rationale: str):
    existing = (
        db.query(ReviewClassification)
        .filter_by(review_id=review_id)
        .first()
    )
    if existing:
        return existing

    classification_obj = ReviewClassification(
        review_id=review_id,
        category=category,
        classification=classification,
        recurring_issue=recurring_issue,
        confidence=confidence,
        rationale=rationale,
    )
    db.add(classification_obj)
    db.commit()
    db.refresh(classification_obj)
    return classification_obj


def get_classifications_for_review(db: Session, review_id: int):
    return db.query(ReviewClassification).filter(
        ReviewClassification.review_id == review_id
    ).all()
