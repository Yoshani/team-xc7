-- noinspection SqlNoDataSourceInspectionForFile

-- =========================================
-- Database Schema for Context-aware End-to-End Software Development Assistant
-- Compatible with MariaDB
-- =========================================

-- Table: Projects
CREATE TABLE projects
(
    project_id CHAR(36) PRIMARY KEY,
    name       VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table: Functional_Requirements
CREATE TABLE functional_requirements
(
    fr_id       INT AUTO_INCREMENT PRIMARY KEY,
    project_id  CHAR(36) NOT NULL,
    description TEXT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects (project_id)
        ON DELETE CASCADE ON UPDATE CASCADE
);

-- Table: Non_Functional_Requirements
CREATE TABLE non_functional_requirements
(
    nfr_id      INT AUTO_INCREMENT PRIMARY KEY,
    project_id  CHAR(36)     NOT NULL,
    category    VARCHAR(100) NOT NULL,
    description TEXT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects (project_id)
        ON DELETE CASCADE ON UPDATE CASCADE
);

-- Table: Embeddings
CREATE TABLE embeddings
(
    embedding_id INT AUTO_INCREMENT PRIMARY KEY,
    text_type    VARCHAR(50) NOT NULL,
    reference_id INT         NOT NULL,
    embedding    BLOB        NOT NULL,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table: Seed_FR_NFR_Pairs (RAG)
CREATE TABLE seed_FR_NFR_pairs
(
    pair_id         INT AUTO_INCREMENT PRIMARY KEY,
    fr_example      TEXT NOT NULL,
    nfr_example     TEXT NOT NULL,
    source          VARCHAR(255),
    quality_checked BOOLEAN   DEFAULT FALSE,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table: Code_Snapshots
CREATE TABLE code_snapshots
(
    commit_id        CHAR(36)     NOT NULL PRIMARY KEY,
    project_id       CHAR(36)     NOT NULL,
    parent_commit_id CHAR(36),
    developer_name   VARCHAR(100) NOT NULL,
    code_text        LONGTEXT     NOT NULL,
    language         VARCHAR(50)  NOT NULL,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects (project_id)
        ON DELETE CASCADE ON UPDATE CASCADE
);

-- Table: Code_Review_Suggestions
CREATE TABLE code_review_suggestions
(
    review_id  INT AUTO_INCREMENT PRIMARY KEY,
    commit_id  CHAR(36) NOT NULL,
    line_start INT,
    line_end   INT,
    suggestion TEXT     NOT NULL,
    severity   VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (commit_id) REFERENCES code_snapshots (commit_id)
        ON DELETE CASCADE ON UPDATE CASCADE
);

-- Table: Review_Classifications
CREATE TABLE review_classifications
(
    classification_id INT AUTO_INCREMENT PRIMARY KEY,
    review_id         INT           NOT NULL,
    category          VARCHAR(100),           -- classification category (e.g., Documentation, Code Quality, etc.)
    classification    VARCHAR(50)   NOT NULL, -- e.g., accepted, modified, not_handled
    recurring_issue   VARCHAR(255),           -- e.g., "Improper error handling"
    confidence        DECIMAL(3, 2) NOT NULL, -- 0.00 - 1.00
    rationale         TEXT,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_review_classification UNIQUE (review_id),
    FOREIGN KEY (review_id) REFERENCES code_review_suggestions (review_id)
        ON DELETE CASCADE
);


-- Table: Risk_Assessments
CREATE TABLE risk_assessments
(
    risk_id              INT AUTO_INCREMENT PRIMARY KEY,
    project_id           CHAR(36) NOT NULL,
    commit_id            CHAR(36) NOT NULL,
    FR_completion_score  DECIMAL(5, 2),
    NFR_completion_score DECIMAL(5, 2),
    compilation_rate     DECIMAL(5, 2),
    final_score          DECIMAL(5, 2),
    recommendation       TEXT,
    rationale            TEXT,
    created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects (project_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (commit_id) REFERENCES code_snapshots (commit_id)
        ON DELETE CASCADE ON UPDATE CASCADE
);

-- Table: Productivity_Metrics
CREATE TABLE productivity_metrics
(
    metric_id    INT AUTO_INCREMENT PRIMARY KEY,
    review_id    INT,
    commit_id    CHAR(36)     NOT NULL,
    metric_name  VARCHAR(100) NOT NULL,
    metric_value VARCHAR(255),
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (review_id) REFERENCES code_review_suggestions (review_id)
        ON DELETE SET NULL ON UPDATE CASCADE,
    FOREIGN KEY (commit_id) REFERENCES code_snapshots (commit_id)
        ON DELETE CASCADE ON UPDATE CASCADE
);

-- Table: System_Logs
CREATE TABLE system_logs
(
    log_id     INT AUTO_INCREMENT PRIMARY KEY,
    component  VARCHAR(100) NOT NULL,
    action     VARCHAR(100) NOT NULL,
    details    TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
