# 🌿 EcoRecon AI

**Enterprise EPR (Extended Producer Responsibility) Compliance & Reconciliation Platform**

> Built for **GreenPack Industries** — a plastic packaging manufacturer that must comply with India's **Plastic Waste Management Rules, 2016 (as amended through 2023)**. The "2016" refers to when the law was originally enacted; it has since been updated in 2018, 2020, and 2023 with stricter thresholds, digital reporting mandates, and enhanced penalties.

---

## 📌 What Does This Application Do?

In simple terms: **EcoRecon AI helps companies prove they are being honest about their plastic usage.**

Under Indian environmental law, companies that manufacture or use plastic packaging must submit monthly reports declaring how much plastic they used. The government then checks these declarations against the company's actual purchase records (from their ERP system) to make sure the numbers match.

EcoRecon AI automates this entire process:

| Step | What Happens | Who Benefits |
|------|-------------|--------------|
| **1. Submit Declaration** | The compliance officer enters how much plastic was used this month (rigid, flexible, multilayer) | Compliance Team |
| **2. Auto-Reconciliation** | The system compares the declared amounts against actual ERP procurement records using pure math (no AI guessing) | Audit Team |
| **3. Flag Mismatches** | If the numbers differ by more than 5% (or 3% for multilayer plastic), it raises a red flag with severity levels | Management |
| **4. AI Narrative** | An AI generates a professional written summary explaining the findings — suitable for regulatory submission | Regulators (CPCB/SPCB) |
| **5. Policy Q&A** | Anyone can ask plain-English questions about compliance rules and get grounded, citation-backed answers | Everyone |

---

## 🚀 Key Features

### 🔢 Deterministic Reconciliation Engine
The mismatch detection is **100% math-based** — no AI is involved in calculating whether numbers match. This is a deliberate design choice: when it comes to compliance audits, you need **certainty, not probability**. The variance formula is:

```
Variance (%) = |Declared Quantity - Procured Quantity| / Procured Quantity × 100
```

If variance exceeds **5%** for rigid/flexible plastic or **3%** for multilayer plastic, it is flagged.

### 🛡️ Hallucination-Safe RAG Pipeline
When you ask the Compliance Policy QA a question, the system:
1. **Searches** the compliance documents using vector similarity (not keyword matching)
2. **Compresses** the results to only the most relevant sentences
3. **Generates** a detailed answer using the AI model
4. **Validates** that every claim in the answer has a real citation from the documents
5. **Rejects** the answer entirely if the AI fabricated any information — returning a safe fallback instead

### 🤖 LangGraph Workflow Orchestration
Instead of letting the AI "think freely," we use LangGraph to enforce a **strict, predictable workflow**:

```
Fetch Declaration → Load ERP Data → Reconcile (Math) → Generate Narrative (AI) → Build Response
```

Every step runs in a fixed order. The AI is only allowed to narrate the results — never to compute them.

### 📊 Premium Dark-Theme Dashboard
A Streamlit-based enterprise dashboard with:
- Real-time API health monitoring
- Interactive declaration submission forms
- Colour-coded reconciliation comparison matrix with severity tiers
- Conversational compliance Q&A with cited source documents

### ✅ Evaluation-Driven AI Engineering
We treat AI outputs like unit-testable code using **DeepEval**:
- **Faithfulness Test** — Does every claim exist in the retrieved context?
- **Hallucination Test** — Did the AI invent any facts?
- **Answer Relevancy Test** — Is the answer actually about the question asked?
- **Context Precision Test** — Did the vector search surface the right documents?

---

## 🧠 AI Model Choices & Reasoning

### Large Language Model (LLM): Groq — Llama 4 Scout 17B

| Attribute | Detail |
|-----------|--------|
| **Model** | `meta-llama/llama-4-scout-17b-16e-instruct` |
| **Provider** | Groq Cloud (inference API) |
| **Parameters** | 17 Billion |

**Why this model?**
- **Speed**: Groq's custom LPU (Language Processing Unit) hardware delivers responses in milliseconds — critical for a compliance tool where officers need answers quickly, not minutes later.
- **Cost-Effective**: Groq's free tier is generous enough for development and demo, and production pricing is significantly cheaper than GPT-4 or Claude.
- **Open-Source Foundation**: Built on Meta's Llama 4, which is open-source — meaning no vendor lock-in and full transparency into model behaviour.
- **Instruction-Tuned**: The `instruct` variant follows system prompts reliably, which is essential for our strict anti-hallucination rules (e.g., "If you don't know, say so").
- **Right-Sized**: 17B parameters is powerful enough to generate professional compliance narratives, but small enough to run affordably at scale. We don't need GPT-4's 1.8 trillion parameters for document-grounded Q&A.

### Embedding Model: Ollama — `nomic-embed-text`

| Attribute | Detail |
|-----------|--------|
| **Model** | `nomic-embed-text` |
| **Provider** | Ollama (runs 100% locally on your machine) |
| **Dimensions** | 768 |

**Why this model?**
- **Runs Locally**: No data ever leaves your machine. For a compliance platform dealing with sensitive regulatory data, this is critical — we don't want procurement numbers being sent to external APIs for embedding.
- **Free Forever**: No API costs. Ollama is open-source and the model runs on your own hardware.
- **High Quality**: Nomic Embed Text consistently ranks among the top open-source embedding models on the MTEB benchmark, performing comparably to OpenAI's `text-embedding-3-small` for document retrieval tasks.
- **Fast**: Small model footprint means embeddings are generated in milliseconds, enabling real-time document search.
- **Long Context**: Supports up to 8,192 tokens per chunk — more than enough for our 500-character compliance document chunks.

---

## 💾 Storage & Vector Store Choices

### Relational Database: SQLite (via aiosqlite + SQLAlchemy 2.0 Async)

| Attribute | Detail |
|-----------|--------|
| **Database** | SQLite |
| **ORM** | SQLAlchemy 2.0 (fully async) |
| **Driver** | aiosqlite |
| **File** | `ecorecon.db` (project root) |

**Why SQLite?**
- **Zero Infrastructure**: No PostgreSQL/MySQL server to install or manage. The entire database is a single file — perfect for a demo platform.
- **Reliable**: SQLite is used by every Android phone, every iPhone, every Mac, every Firefox browser, and most Python applications. It handles millions of records without breaking.
- **Async-Ready**: With `aiosqlite`, we get non-blocking database operations that don't slow down the FastAPI server while waiting for reads/writes.
- **Portable**: Clone the repo, and the database travels with it. No connection strings to configure (beyond the file path).

**What it stores**: Declaration submissions, reconciliation audit logs, category breakdowns, timestamps, and user audit trails.

### Vector Database: ChromaDB (Persistent Mode)

| Attribute | Detail |
|-----------|--------|
| **Vector Store** | ChromaDB |
| **Mode** | Persistent (data survives restarts) |
| **Storage Path** | `data/chroma_db/` |
| **Collection** | `epr_compliance_docs` |

**Why ChromaDB?**
- **Python-Native**: ChromaDB is written in Python and integrates seamlessly with LangChain — no Docker containers, no Java runtimes, no external services.
- **Persistent Storage**: Unlike FAISS (which is in-memory only by default), ChromaDB persists vectors to disk. When you restart the server, your compliance document embeddings are still there.
- **Metadata Filtering**: We can attach metadata (source document name, section number) to each chunk and filter during retrieval — critical for citation validation.
- **Lightweight**: Runs in-process alongside the FastAPI server. No separate database server needed.
- **Production-Ready**: Chroma also offers a cloud-hosted option if GreenPack scales beyond a single-server deployment in the future.

---

## 🤖 AI Coding Assistant Usage

This project was built with the assistance of **Google Gemini (Antigravity IDE)** — an AI pair-programming assistant integrated directly into the development environment.

### Where the AI Assistant Helped

| Area | How AI Assisted |
|------|----------------|
| **Architecture Design** | Helped design the deterministic-first architecture, ensuring clear separation between math-based reconciliation and AI narrative generation |
| **Skill-Based Scaffolding** | Used pre-built skill files (`.agents/skills/`) to maintain consistency across FastAPI routes, LangGraph nodes, RAG pipelines, and Streamlit components |
| **Prompt Engineering** | Co-authored the hallucination-safe RAG prompts (`app/prompts/rag_prompt.py`) with strict anti-fabrication rules and citation validation |
| **Debugging** | Identified and fixed a status-code mismatch between the FastAPI backend (HTTP 201) and Streamlit frontend (expecting HTTP 200) that caused false error messages |
| **Code Review** | Validated that no business logic leaked into route handlers and no LLM calls leaked into reconciliation math |
| **Documentation** | Assisted in writing this README and inline docstrings throughout the codebase |

### What the AI Did NOT Do
- **No auto-generated business logic**: Every reconciliation formula, threshold, and escalation rule was explicitly defined by the developer based on the PWM Rules, 2016.
- **No unsupervised code merges**: Every AI suggestion was reviewed, tested, and approved by the developer before being applied.

---

## 📦 Project Structure

```text
ecorecon_ai/
│
├── app/                          # ── FastAPI Backend ──
│   ├── api/                      # HTTP route handlers (submit, summary, ask)
│   ├── core/                     # Settings, logging, exception handlers
│   ├── database/                 # SQLAlchemy ORM models, async session management
│   ├── graph/                    # LangGraph workflow orchestration (DAG nodes)
│   ├── prompts/                  # LLM prompt templates (hallucination-safe)
│   ├── rag/                      # Advanced retrieval, chunking, ChromaDB management
│   ├── repositories/             # Database persistence layer (repository pattern)
│   ├── schemas/                  # Pydantic v2 request/response validation
│   ├── services/                 # Business logic, ERP loading, LLM service, HallucinationGuard
│   └── main.py                   # Application factory & lifespan management
│
├── frontend/                     # ── Streamlit Dashboard ──
│   ├── components/               # Tab modules (analytics, ingestion, audit, policy QA)
│   ├── styles/                   # Custom CSS (glassmorphism dark theme)
│   ├── utils/                    # API client, session state management
│   └── main.py                   # Dashboard entrypoint
│
├── data/
│   ├── compliance_docs/          # 📄 EPR regulation markdown files (RAG knowledge base)
│   │   ├── pwm_rules.md          #    → Plastic Waste Management Rules, 2016
│   │   ├── compliance_sop.md     #    → GreenPack internal compliance SOP
│   │   └── cpcb_guidelines.md    #    → CPCB enforcement guidelines
│   ├── erp/                      # 📊 Mock ERP procurement CSV feeds
│   └── chroma_db/                # 🔍 ChromaDB persistent vector index
│
├── evaluation/
│   └── deepeval/                 # ✅ AI quality tests (faithfulness, hallucination, precision)
│
├── tests/                        # 🧪 Pytest unit & integration tests
├── scripts/                      # 🔧 Utility scripts (DB reset, document ingestion)
├── .env                          # Environment configuration (API keys, model settings)
└── pyproject.toml                # Python project config & dependency management (uv)
```

---

## 🛠 Tech Stack Summary

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Backend API** | FastAPI + Pydantic v2 | REST API with automatic validation |
| **Database** | SQLite + SQLAlchemy 2.0 (async) | Structured data persistence |
| **Vector Store** | ChromaDB (persistent) | Semantic document search |
| **LLM** | Groq (Llama 4 Scout 17B) | Narrative generation & policy Q&A |
| **Embeddings** | Ollama (nomic-embed-text) | Local, private document vectorization |
| **AI Orchestration** | LangGraph + LangChain | Strict workflow DAG execution |
| **Frontend** | Streamlit (dark theme) | Enterprise compliance dashboard |
| **AI Evaluation** | DeepEval + Pytest | Continuous AI quality monitoring |
| **Package Manager** | uv | Fast Python dependency resolution |

---

## ⚙️ Setup & Installation

### Prerequisites
- **Python 3.10+**
- **uv** package manager ([install guide](https://docs.astral.sh/uv/getting-started/installation/))
- **Ollama** running locally ([download](https://ollama.ai)) with `nomic-embed-text` model pulled
- **Groq API Key** (free at [console.groq.com](https://console.groq.com))

### Step 1: Install Dependencies
```bash
uv sync --all-extras
```

### Step 2: Configure Environment
Create or edit the `.env` file in the project root:
```env
APP_ENV=development
APP_DEBUG=false
GROQ_API_KEY=gsk_your-api-key-here
GROQ_MODEL=meta-llama/llama-4-scout-17b-16e-instruct
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_EMBED_MODEL=nomic-embed-text
```

### Step 3: Pull the Embedding Model
```bash
ollama pull nomic-embed-text
```

### Step 4: Initialize the Database
```bash
uv run python scripts/reset_db.py
```

### Step 5: Ingest Compliance Documents into Vector Store
```bash
uv run python scripts/ingest_docs.py
```

### Step 6: Start the Backend (Terminal 1)
```bash
uv run uvicorn app.main:app --reload
```
Backend will be available at: **http://localhost:8000** (Swagger docs at `/docs`)

### Step 7: Start the Frontend Dashboard (Terminal 2)
```bash
uv run streamlit run frontend/main.py
```
Dashboard will be available at: **http://localhost:8501**

---

## 📖 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/submit` | Submit a monthly plastic declaration (deterministic validation, no AI) |
| `GET` | `/api/v1/summary/{producer_id}/{month}` | Run reconciliation against ERP data + generate AI narrative |
| `POST` | `/api/v1/ask` | Ask a compliance question (hallucination-safe RAG pipeline) |
| `GET` | `/health` | Container readiness probe |

---

## 🔄 What I Would Do Differently With One More Day

If I had one additional day to improve this project, I would **add a complete user authentication and role-based access control (RBAC) system**. Here's why:

### The Current Gap
Right now, anyone who can access the dashboard can submit declarations, run reconciliations, and query compliance policies. In a real enterprise environment, this is a compliance risk in itself:
- A **Compliance Officer** should be the only person who can submit and certify declarations
- A **Production Manager** should have read-only access to reconciliation results
- An **Auditor** should be able to view audit trails but not modify data
- An **Admin** should manage user permissions

### What I Would Build
1. **JWT-based authentication** with FastAPI's `OAuth2PasswordBearer` — login with username/password, receive a signed token
2. **Role-based middleware** that checks the user's role before allowing access to sensitive endpoints (e.g., only `compliance_officer` role can `POST /submit`)
3. **Audit trail enhancement** — every action (submit, reconcile, query) logged with the authenticated user's identity, not just the IP address
4. **Streamlit login page** — a secure login gate before the dashboard loads, with session management

This would transform EcoRecon AI from a functional demo into a truly enterprise-ready platform where every action is attributable to a specific person — which is exactly what regulators (CPCB/SPCB) expect during compliance audits.

---

## 📜 License

MIT License — See [LICENSE](LICENSE) for details.

---

<p align="center">
  <b>EcoRecon AI</b> — Deterministic-First Compliance Intelligence for GreenPack Industries<br>
  <i>Where Math is Math, and AI is the Narrator.</i>
</p>
