# 🚀 Intelli-Credit: AI-Powered Corporate Credit Decisioning Engine

> **IIT Hackathon 2026 | Theme: Next-Gen Corporate Credit Appraisal — Bridging the Intelligence Gap**

Intelli-Credit is a full-stack, production-grade credit intelligence platform that automates the end-to-end corporate loan appraisal process for Indian SME & mid-corporate lending. It stitches together **structured financials, unstructured documents, and real-time regulatory intelligence** to produce a comprehensive, explainable **Credit Appraisal Memorandum (CAM)** — in seconds, not weeks.

---

## 🏗️ Architecture Overview

The system is built as a **three-pillar microservices architecture** that mirrors the Indian credit manager's mental model.

```
┌──────────────────────────────── FRONTEND (Next.js) ──────────────────────────────────┐
│  Credit Manager: Create Case → Primary Insights → Upload Docs → Pipeline → CAM PDF   │
│  Senior Approver: Review Queue → Approve / Reject / Send Back                         │
└──────────────────────────────────────────────────────────────────────────────────────┘
                                        │ JWT Auth REST API
┌──────────────────────────────── BACKEND (FastAPI :8000) ─────────────────────────────┐
│  Auth   │  Case CRUD   │  File Upload   │  Pipeline Orchestrator   │  CAM Download    │
│         └──────────────┬──────────────────────────────┬────────────┘                  │
└────────────────────────┼──────────────────────────────┼───────────────────────────────┘
               ┌─────────┴──────────┐         ┌─────────┴──────────────────┐
               │                    │         │                            │
┌──────────────▼───────┐  ┌─────────▼──────┐  ┌─────────────────────────▼─┐
│  PILLAR 1: EXTRACTOR │  │ PILLAR 2:       │  │ PILLAR 3: CAM ENGINE       │
│  (subprocess)         │  │ RESEARCH AGENT  │  │ (Python import)            │
│                       │  │ (FastAPI :8001)  │  │                            │
│  PDF / OCR / DOCX    │  │                 │  │  8-dim weighted score      │
│  Excel / CSV         │  │  RBI Defaulter  │  │  Sigmoid normalisation     │
│  LLM Structuring     │  │  MCA21 API      │  │  Amount + Rate Engine      │
│  Cross-Validator     │  │  eCourts        │  │  Gemini Narratives (8 sec) │
│  → Structured JSON   │  │  Tavily News    │  │  → DOCX + PDF CAM          │
└───────────────────────┘  │  GSTN / CIBIL  │  └────────────────────────────┘
                           │  (async, 6 src) │
                           └─────────────────┘
```

---

## 📊 Databricks Integration (Production Data Layer)

> **In a Production deployment, Apache Databricks serves as the central intelligence lake underlying all three pillars.**

| Layer | Databricks Role |
|-------|----------------|
| **Document Ingestion** | Delta Lake stores raw uploaded documents + extracted structured JSON, enabling full audit trail and reprocessing |
| **Research Intelligence** | RBI, MCA, eCourts, GSTN, CIBIL results are persisted as Delta tables — enabling cross-case pattern detection (e.g., flagging DINs that appear in other cases) |
| **Scoring & ML** | The composite credit scoring model can be trained/refined using Databricks MLflow on historical loan portfolio data, replacing the current rules-based weights with data-driven regression |
| **CAM History** | All generated CAMs stored as structured data in Unity Catalog — enabling portfolio-level analytics, acceptance rate trends, and portfolio quality dashboards |
| **Real-time Serving** | Databricks Model Serving exposes the trained scoring model as a REST endpoint, replacing the current in-process scorer |

The hackathon version runs with **SQLite + local file storage** for quick setup. The architecture is explicitly designed so that replacing these with Databricks Delta Lake requires only environment variable changes — all persistence calls are abstracted through repository interfaces.

```
env var: USE_DATABRICKS=true   →  SQLite swaps for Delta Lake
env var: DATABRICKS_HOST=...   →  All SQL calls route to Unity Catalog
env var: MLFLOW_TRACKING_URI=. →  Scoring weights pulled from MLflow registry
```

---

## 🔬 Three-Pillar Design

### Pillar 1 — 📂 Document Intelligence (`/extractor`)

- **Multi-format ingestion**: PDF (text-native + scanned/OCR), DOCX, XLSX, CSV
- **Auto format detection** — routes to the right extractor automatically
- **Gemini 2.0 Flash LLM structuring** — raw text → strict bank-grade JSON schema
- **11-point Cross-Validator** including:
  - **CV-009**: GST Turnover vs Bank Credits (Circular Trading Detector)
  - **CV-010**: ITC Ratio vs Sector Benchmark (Fabricated Input Credit)
  - **CV-011**: **GSTR-2A vs GSTR-3B ITC Reconciliation** (India's most nuanced GST fraud check — auto-populated purchase register vs self-declared return)
  - ICR, Gearing, PAT Margin, Debt Trend, Revenue Consistency, Audit Qualifications

### Pillar 2 — 🔍 Research Intelligence (`/research_agent`)

6 concurrent async sources orchestrated via `asyncio.gather`:

| Source | What it checks | Hard Reject? |
|--------|---------------|-------------|
| **RBI Defaulter** | Wilful defaulter list — company + all promoters | ✅ Auto-reject on hit |
| **MCA21** | ROC filings, open charges, struck-off director companies | — |
| **eCourts** | Criminal + civil cases — company + all promoters | Criminal = CRITICAL |
| **Tavily News** | Fraud, insolvency, NPA, rating downgrade signals | — |
| **GSTN** | GST registration status | — |
| **CIBIL Commercial** | C-MAP score 300–900, DPD, enquiry count | — |

**Demo Fallback Mode**: When live portals are unreachable (e.g., during hackathon demo), `DEMO_MODE=1` (default) automatically returns realistic cached data — ensuring a flawless presentation even with network issues.

### Pillar 3 — 🧠 CAM Engine (`/cam_engine`)

- **8-dimension composite score** with sigmoid normalisation (Capacity 25% · Capital 20% · Character 20% · Collateral 15% · Conditions 10% · GST Quality 5% · Litigation 3% · MCA 2%)
- **Primary Insight adjustment** ±15 pts — credit officer field observations (factory visit, management quality, CIBIL score)
- **Cross-pillar contradiction detector** — e.g., *"Strong GSTR-3B compliance but ₹48L bank statement mismatch — circular trading suspected"*
- **Transparent interest rate chain** — every basis point premium justified by a specific risk finding
- **Gemini 2.0 Flash** generates 8 CAM sections including the Decision Rationale narrative
- **Output**: Professional DOCX + PDF CAM with standard Indian bank format (10 sections, cover page, Five Cs, GSTR-2A analysis, Risk Matrix, Rate Derivation, AI Audit Trail)

---

## 🖥️ Frontend (`/frontend`)

Full **role-based** Next.js dashboard:

| Role | Capabilities |
|------|-------------|
| **Credit Manager** | Create case → Enter primary insights (factory visit) → Upload documents → Monitor AI pipeline → View CAM → Forward to Approver |
| **Senior Approver** | Review queue → Read full CAM → Approve / Reject / Send Back with comments |

---

## 🛠️ Quick Start

### ⚡ One-Click (Windows)

```bat
./start_all.bat
```

Opens **http://localhost:3000** — sign up as Credit Manager or Senior Approver and start a case.

### 🔧 Manual Setup

```bash
# Backend
cd backend && pip install -r requirements.txt
python main.py                        # :8000

# Research Agent
cd research_agent && pip install -r requirements.txt
python -m uvicorn api.main:app --port 8001

# Frontend
cd frontend && npm install && npm run dev   # :3000
```

---

## 🔐 Environment Variables

| Variable | Service | Purpose |
|----------|---------|---------|
| `GEMINI_API_KEY` | Backend, CAM Engine, Extractor | LLM for structuring + narratives |
| `TAVILY_API_KEY` | Research Agent | News & threat signal search |
| `JWT_SECRET` | Backend | Token signing |
| `DEMO_MODE` | Research Agent | `1` (default) = enable fallback data when portals fail |
| `REPO_RATE` | CAM Engine | RBI Repo Rate (default 6.50%) |
| `BANK_SPREAD` | CAM Engine | MCLR Spread (default 3.00%) |
| `DATABRICKS_HOST` | All | *(Production)* Unity Catalog endpoint |
| `USE_DATABRICKS` | All | *(Production)* `true` → swap SQLite for Delta Lake |

---

## 📋 CAM Document Format

The generated PDF CAM follows **standard Indian bank Credit Appraisal Memorandum layout**:

```
Cover Page (Decision Box + Metadata)
│
├── Section 1:  Executive Summary & Recommendation
├── Section 2:  Company Profile + Promoter Table
├── Section 3:  Character (C1) — RBI, MCA, eCourts, News
├── Section 4:  Capacity (C2) — 3-Year Financials, DSCR, ICR
├── Section 5:  Capital (C3) — Net Worth, D/E, Gearing
├── Section 6:  Collateral (C4) — Asset Schedule, Coverage Ratios
├── Section 7:  Conditions (C5) — Sector Outlook, Regulatory
├── Section 7A: ★ GST Intelligence — GSTR-2A vs 3B Reconciliation [CV-011]
│                                  — GST vs Bank Mismatch [CV-009]
│                                  — ITC Ratio vs Sector Benchmark [CV-010]
├── Section 8:  Risk Matrix (All Flags + Mitigants)
├── Section 9:  Recommendation — Amount Derivation + Rate Chain + Covenants
└── Section 10: ★ Decision Rationale & AI Explainability Audit Trail
                 — 8-Dimension Score Table
                 — Composite Score Derivation
                 — Primary Insight Adjustments [±15 pts]
                 — Cross-Pillar Contradictions
                 — Gemini Decision Rationale Narrative
                 — Five Cs Final Summary
```

---

## ✅ Hackathon Checklist

- [x] **Multi-format document ingestion** — PDF (text + scanned), DOCX, Excel, CSV
- [x] **GSTR-2A vs GSTR-3B reconciliation** — India-specific fraud check, prominently called out in CAM Section 7A
- [x] **6-source concurrent research** — RBI, MCA21, eCourts, Tavily, GSTN, CIBIL
- [x] **Primary Insights portal** — credit officer field observations with live score preview
- [x] **Explainable composite score** — every decision point traceable, cited in CAM Section 10
- [x] **PDF CAM download** — standard Indian bank format
- [x] **Role-based approval workflow** — Credit Manager + Senior Approver
- [x] **Demo Fallback Mode** — smooth presentation even if external portals are down
- [x] **Databricks integration path** — designed for lift-and-shift to Delta Lake in production

---

*Developed for IIT Hackathon 2026 · Theme: Next-Gen Corporate Credit Appraisal*
