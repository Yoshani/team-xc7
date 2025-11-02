# Context-aware End-to-End Software Development Assistant – Backend

This repository contains the **backend service** and Web Dashboard for the Context-aware End-to-End Software Development Assistant — an AI-powered platform that connects requirement generation, code completion, code quality checks, productivity metrics, and project risk assessment into a single, unified ecosystem.

---

## Overview

Modern software development often suffers from fragmented tools and disconnected workflows across requirements, coding, and project management.  
This backend aims to bridge that gap by offering:
- Automated **Non-Functional Requirement (NFR)** generation from Functional Requirements (FRs)
- Intelligent **code review** and **quality metric tracking**
- **Developer productivity analytics** based on code review data
- **Project risk assessment** using real-time compilation and behavioral metrics
- RESTful APIs for integration with the frontend dashboard and future IDE plugins

---

## System Architecture

The backend forms the core processing layer of the system and interacts with:

- **Frontend (Streamlit Dashboard)** — visualizes metrics and insights
- **Database Layer** — stores FRs, NFRs, and developer analytics
- **LLM & RAG Pipeline** — powers NFR and code intelligence generation
- **Code Repositories** — source for review and productivity data

