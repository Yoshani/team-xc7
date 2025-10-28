"""
CRUD operations for DB
"""
from __future__ import annotations

from typing import List, Dict, Any

from sqlalchemy import Column, String, Integer, Text, DateTime, DECIMAL, ForeignKey, func, text
from sqlalchemy.orm import relationship, Session

from .connection import Base, engine


# ==========================
# Models
# ==========================

class Project(Base):
    __tablename__ = "projects"

    project_id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, server_default=func.now())


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


class FunctionalRequirement(Base):
    __tablename__ = "functional_requirements"

    fr_id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String(36), nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, server_default=func.now())


class NonFunctionalRequirement(Base):
    __tablename__ = "non_functional_requirements"

    nfr_id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String(36), nullable=False)
    category = Column(String(100))
    description = Column(Text)
    created_at = Column(DateTime, server_default=func.current_timestamp())


class RiskAssessment(Base):
    __tablename__ = "risk_assessments"

    risk_id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String(36), nullable=False)
    commit_id = Column(String(36), ForeignKey("code_snapshots.commit_id"), nullable=False)
    FR_completion_score = Column(DECIMAL(5, 2))
    NFR_completion_score = Column(DECIMAL(5, 2))
    compilation_rate = Column(DECIMAL(5, 2))
    final_score = Column(DECIMAL(5, 2))
    recommendation = Column(Text)
    rationale = Column(Text)
    created_at = Column(DateTime, server_default=func.now())

    snapshot = relationship("CodeSnapshot", backref="risk_assessments")

# ==========================
# Create tables (one-time init)
# ==========================
def init_db():
    Base.metadata.create_all(bind=engine)


# ==========================
# CRUD Operations
# ==========================

# --- Snapshots ---
def create_snapshot(db: Session, project_id: str, commit_id: str, parent_commit_id: str,
                    developer_name: str, code_text: str, language: str) -> CodeSnapshot:
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
    """
    Create a new review classification entry.
    :param db: SQLAlchemy session
    :param review_id: Review ID
    :param category: Category of the classification
    :param classification: Classification label (accepted/modified/not_handled)
    :param recurring_issue: Recurring issue description
    :param confidence: Confidence score (0.0 to 1.0)
    :param rationale: Rationale for the classification
    :return: Created or existing ReviewClassification object
    """
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
    """
    Fetch all classifications for a given review ID.
    :param db: SQLAlchemy session
    :param review_id: Review ID to fetch classifications for
    :return: Classifications list
    """
    return db.query(ReviewClassification).filter(
        ReviewClassification.review_id == review_id
    ).all()


def get_all_classifications_with_snapshot_info(db: Session):
    """
    Fetch all review classifications along with developer name and snapshot creation date.

    :param db: SQLAlchemy session
    :return: List of tuples (ReviewClassification, developer_name, snapshot_date)
    """
    return (
        db.query(
            ReviewClassification,
            CodeSnapshot.developer_name,
            CodeSnapshot.created_at.label("snapshot_date")
        )
        .join(CodeReviewSuggestion, ReviewClassification.review_id == CodeReviewSuggestion.review_id)
        .join(CodeSnapshot, CodeSnapshot.commit_id == CodeReviewSuggestion.commit_id)
        .all()
    )


def save_functional_requirements(db: Session, project_id: str, fr_list: list[str]) -> int:
    """
    Save a list of functional requirements for a given project ID.
    :param db: SQLAlchemy session
    :param project_id: Project UUID
    :param fr_list: List of functional requirement titles/descriptions
    :return: Number of rows inserted
    """
    count = 0
    for fr in fr_list:
        fr_obj = FunctionalRequirement(
            project_id=project_id,
            description=fr
        )
        db.add(fr_obj)
        count += 1
    db.commit()
    return count


def get_functional_requirements_by_project(db: Session, project_id: str):
    """
    Retrieves all functional requirements for a given project.
    :param db: SQLAlchemy session
    :param project_id: Project UUID
    :return: List of FunctionalRequirement objects
    """
    return db.query(FunctionalRequirement).filter(FunctionalRequirement.project_id == project_id).all()


def get_non_functional_requirements_by_project(db: Session, project_id: str):
    """
    Retrieves all non-functional requirements for a given project.
    :param db: SQLAlchemy session
    :param project_id: Project UUID
    :return: List of NonFunctionalRequirement objects
    """
    return db.query(NonFunctionalRequirement).filter(NonFunctionalRequirement.project_id == project_id).all()


def create_risk_assessment(db: Session, project_id: str, commit_id: str, fr_score: float, nfr_score: float,
                           compilation_rate: float, final_score: float,
                           recommendation: str, rationale: str) -> RiskAssessment:
    """
    Creates and saves a new risk assessment entry.
    :param db: SQLAlchemy session
    :param project_id: Associated project ID
    :param commit_id: Associated commit ID
    :param fr_score: Functional requirement completion score
    :param nfr_score: Non-functional requirement completion score
    :param compilation_rate: Compilation success rate
    :param final_score: Final aggregated risk score
    :param recommendation: System recommendation (e.g., 'Go', 'No-Go')
    :param rationale: Explanation behind the decision
    :return: Created RiskAssessment object
    """
    risk = RiskAssessment(
        project_id=project_id,
        commit_id=commit_id,
        FR_completion_score=fr_score,
        NFR_completion_score=nfr_score,
        compilation_rate=compilation_rate,
        final_score=final_score,
        recommendation=recommendation,
        rationale=rationale
    )
    db.add(risk)
    db.commit()
    db.refresh(risk)
    return risk


def get_risk_assessments_by_project(db: Session, project_id: str):
    """
    Retrieves all risk assessments for a given project by joining code_snapshots.
    :param db: SQLAlchemy session
    :param project_id: Project UUID
    :return: Latest RiskAssessment object or None if not found
    """
    return (
        db.query(RiskAssessment)
        .filter(RiskAssessment.project_id == project_id)
        .order_by(RiskAssessment.created_at.desc())
        .first()
    )


def get_latest_snapshot_by_project(db: Session, project_id: str) -> CodeSnapshot | None:
    """
    Fetches the most recent code snapshot for a given project.
    :param db: SQLAlchemy session
    :param project_id: Project UUID
    :return: Latest CodeSnapshot object or None if not found
    """
    return (
        db.query(CodeSnapshot)
        .filter(CodeSnapshot.project_id == project_id)
        .order_by(CodeSnapshot.created_at.desc())
        .first()
    )

def get_project_by_id(db: Session, project_id: str) -> Project | None:
    """
    Fetches a project by its ID.
    :param db: SQLAlchemy session
    :param project_id: Project UUID
    :return: Project object or None if not found
    """
    return db.query(Project).filter(Project.project_id == project_id).first()

def create_project(db: Session, project_id: str, name: str) -> Project:
    """
    Creates a new project entry.
    :param db: SQLAlchemy session
    :param project_id: Project UUID
    :param name: Project name
    :return: Created Project object
    """
    project = Project(
        project_id=project_id,
        name=name
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def _as_str(x) -> str:
    if x is None:
        return ""
    if isinstance(x, (str, int, float)):
        return str(x)
    if isinstance(x, list):
        return "\n".join(_as_str(i) for i in x if i is not None)
    if isinstance(x, dict):
        # Build a sensible text if we get a dict instead of a string:
        # prefer "statement", else try a few common keys, else flatten.
        for k in ("statement", "requirement", "description", "text", "spec", "content"):
            if k in x and x[k]:
                return _as_str(x[k])
        parts = []
        if "title" in x and x["title"]:
            parts.append(str(x["title"]))
        if "rationale" in x and x["rationale"]:
            parts.append("Rationale: " + _as_str(x["rationale"]))
        if "acceptance_criteria" in x and x["acceptance_criteria"]:
            parts.append("Acceptance Criteria:\n" + _as_str(x["acceptance_criteria"]))
        if "metrics" in x and x["metrics"]:
            parts.append("Measures:\n" + _as_str(x["metrics"]))
        if parts:
            return "\n\n".join(parts)
        return "\n".join(f"{k}: {v}" for k, v in x.items() if v is not None)
    return str(x)


def save_nfrs_statement_to_description(
        db: Session, project_id: str, items: List[Dict[str, Any]]
) -> int:
    """
    Persist NFRs into non_functional_requirements mapping:
      description := item['statement']
      category    := item.get('category')
    Skips rows with empty/missing 'statement'.
    """
    if not items:
        return 0

    inserted = 0
    for it in items:
        if not isinstance(it, dict):
            continue
        statement = (it.get("statement") or "").strip()
        if not statement:
            continue
        category = it.get("category")
        if category is not None:
            category = str(category)[:100]

        db.execute(
            text(
                "INSERT INTO non_functional_requirements (project_id, category, description) "
                "VALUES (:project_id, :category, :description)"
            ),
            {
                "project_id": project_id,
                "category": category,
                "description": statement,
            },
        )
        inserted += 1

    if inserted:
        db.commit()
    return inserted


def save_nfrs(db: Session, project_id: str, nfr_items: list[dict | str], *, skip_empty: bool = True) -> int:
    """
    Save NFRs into non_functional_requirements.
    - Primary text comes from `statement`.
    - Falls back gracefully to other fields if shape differs.
    """
    to_insert = []
    for nfr in (nfr_items or []):
        # CATEGORY
        category = None
        if isinstance(nfr, dict):
            category = nfr.get("category") or nfr.get("type") or nfr.get("group") or None
            if not category and isinstance(nfr.get("tags"), list) and nfr["tags"]:
                category = str(nfr["tags"][0])
            if category:
                category = str(category)[:100]

        # DESCRIPTION (use statement first!)
        if isinstance(nfr, dict) and "statement" in nfr and nfr["statement"]:
            description = _as_str(nfr["statement"])
        else:
            # fallback: try other keys or compose
            description = _as_str(nfr)

        description = (description or "").strip()

        if skip_empty and not description:
            continue

        to_insert.append(
            NonFunctionalRequirement(
                project_id=project_id,
                category=category,
                description=description
            )
        )

    if not to_insert:
        return 0

    db.add_all(to_insert)
    db.commit()
    return len(to_insert)
