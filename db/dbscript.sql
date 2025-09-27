-- =========================================
-- Database Schema for Context-aware End-to-End Software Development Assistant
-- Compatible with MariaDB
-- =========================================

-- Table: Functional_Requirements
CREATE TABLE functional_requirements (
    fr_id INT AUTO_INCREMENT PRIMARY KEY,
    project_id BINARY(16) NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table: Non_Functional_Requirements
CREATE TABLE non_functional_requirements (
    nfr_id INT AUTO_INCREMENT PRIMARY KEY,
    project_id BINARY(16) NOT NULL,
    category VARCHAR(100) NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table: Embeddings
CREATE TABLE embeddings (
    embedding_id INT AUTO_INCREMENT PRIMARY KEY,
    text_type VARCHAR(50) NOT NULL,
    reference_id INT NOT NULL,
    embedding BLOB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table: Seed_FR_NFR_Pairs (RAG)
CREATE TABLE seed_FR_NFR_pairs (
    pair_id INT AUTO_INCREMENT PRIMARY KEY,
    fr_example TEXT NOT NULL,
    nfr_example TEXT NOT NULL,
    source VARCHAR(255),
    quality_checked BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table: Code_Snapshots
CREATE TABLE code_snapshots (
    commit_id BINARY(16) NOT NULL PRIMARY KEY,
    project_id BINARY(16) NOT NULL,
    parent_commit_id BINARY(16),
    developer_name VARCHAR(100) NOT NULL,
    code_text LONGTEXT NOT NULL,
    language VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table: Code_Review_Suggestions
CREATE TABLE code_review_suggestions (
    review_id INT AUTO_INCREMENT PRIMARY KEY,
    commit_id BINARY(16) NOT NULL,
    line_start INT,
    line_end INT,
    suggestion TEXT NOT NULL,
    category VARCHAR(50),
    severity VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (commit_id) REFERENCES code_snapshots(commit_id)
        ON DELETE CASCADE ON UPDATE CASCADE
);

-- Table: Risk_Assessments
CREATE TABLE risk_assessments (
    risk_id INT AUTO_INCREMENT PRIMARY KEY,
    commit_id BINARY(16) NOT NULL,
    FR_completion_score DECIMAL(5,2),
    NFR_completion_score DECIMAL(5,2),
    compilation_rate DECIMAL(5,2),
    final_score DECIMAL(5,2),
    recommendation TEXT,
    rationale TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (commit_id) REFERENCES code_snapshots(commit_id)
        ON DELETE CASCADE ON UPDATE CASCADE
);

-- Table: Productivity_Metrics
CREATE TABLE productivity_metrics (
    metric_id INT AUTO_INCREMENT PRIMARY KEY,
    review_id INT,
    commit_id BINARY(16) NOT NULL,
    metric_name VARCHAR(100) NOT NULL,
    metric_value VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (review_id) REFERENCES code_review_suggestions(review_id)
        ON DELETE SET NULL ON UPDATE CASCADE,
    FOREIGN KEY (commit_id) REFERENCES code_snapshots(commit_id)
        ON DELETE CASCADE ON UPDATE CASCADE
);

-- Table: System_Logs
CREATE TABLE system_logs (
    log_id INT AUTO_INCREMENT PRIMARY KEY,
    component VARCHAR(100) NOT NULL,
    action VARCHAR(100) NOT NULL,
    details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =========================================
-- Notes:
-- 1. project_id and commit_id are stored as BINARY(16) to hold UUIDs efficiently.
-- 2. AUTO_INCREMENT used for primary keys like fr_id, nfr_id, etc.
-- 3. LONGTEXT for code_text to handle large code snapshots.
-- 4. DECIMAL(5,2) / DECIMAL(10,2) used for metric scores.
-- 5. Foreign keys ensure relational integrity.
-- =========================================