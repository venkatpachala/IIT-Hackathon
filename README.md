# 🚀 Intelli-Credit: AI-Powered Credit Decisioning Engine

Intelli-Credit is a next-generation, automated credit appraisal and due-diligence platform designed for Indian SME lending. It combines deep document intelligence with real-time regulatory research to provide a comprehensive risk profile of any business entity within seconds.

---

## 🏗️ Architecture Overview

The system is built as a **decoupled, modular microservices architecture** to ensure scalability and robustness:

### 1. 📂 Ingestion Layer (`/extractor`)
*   **Multi-Format Support:** Ingests PDF (Text & Scanned OCR), DOCX, XLSX, and CSV.
*   **Intelligent Router:** Automatically detects file types and routes to specialized extractors (e.g., `pdfplumber` for text, `pytesseract` for OCR).
*   **LLM Structuring:** Uses Claude 3.5 Sonnet / GPT-4o to transform raw text into a strict bank-grade JSON schema.
*   **Cross-Validation:** Automatically verifies financial data consistency across different parts of the ingested documents.

### 2. 🔍 Research Agent (`/research_agent`)
*   **5-Source Orchestrator:** Performs concurrent, asynchronous lookups across:
    *   **RBI:** Wilful Defaulter lists.
    *   **MCA21:** ROC filings, charges, and director history.
    *   **eCourts:** Litigation and legal history.
    *   **GSTN:** Registration status and filing consistency.
    *   **Intelligence News:** Real-time sentiment analysis for fraud/NPA signals (via Tavily).
*   **Proprietary Scoring:** Computes a risk score (0-100) and assigns a Risk Band (Green, Amber, Red, Black/Auto-Reject).

---

## ✅ Current Status: Milestone 2 Complete

We have successfully completed the core backend integration:
- [x] **Decoupled Architecture:** Extractor and Research Agent now operate as independent services.
- [x] **API Integration:** Research Agent is exposed as a FastAPI service with validated input/output contracts.
- [x] **Full Pipeline Integration:** Demonstrated data flow from PDF ingestion → Entity Extraction → 5-Source Research → Final Credit Score.
- [x] **Clean Repository:** Implemented comprehensive `.gitignore` and removed environment bloat.
- [x] **Performance Metrics:** Initial benchmarkings completed (documented in `METRICS.md`).

---

## 🛠️ Getting Started

### Prerequisites
- Python 3.11+
- Tesseract OCR (for scanned PDF support)
- Poppler (for PDF rendering)

### Setup
1. **Clone the repo:**
   ```bash
   git clone https://github.com/venkatpachala/IIT-Hackathon.git
   cd IIT-Hackathon
   ```
2. **Configure Environment:** Create a `.env` file in both `/extractor` and `/research_agent` directories (refer to `.env.example`).
3. **Install Dependencies:**
   ```bash
   # For Extractor
   cd extractor && pip install -r requirements.txt
   # For Research Agent
   cd ../research_agent && pip install -r requirements.txt
   ```

### Running the Services
*   **Extractor Demo:** `python extractor/main.py --demo`
*   **Research Agent API:** `cd research_agent && python api/main.py`

---

## ⏩ What's Next?

### 1. 🖥️ Frontend Orchestration
Developing a unified Dashboard that coordinates calls between the Ingestion Layer and Research Agent, providing a "single pane of glass" for credit officers.

### 2. 🗄️ Persistence Layer
Integrating a centralized Database (PostgreSQL) to store generated credit reports, audit logs, and historical trends for company profiles.

### 3. 🛡️ Advanced Rule Engine
Implementing more granular "Hard-Stop" rules and weighted scoring logic based on specific banking compliance standards.

### 4. 🐳 Deployment & CI/CD
Full containerization using Docker and Docker Compose for seamless cloud deployment and automated testing pipelines.

---

**Developed for IIT Hackathon 2026**
