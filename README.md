# 🛒 Voice Shopping Assistant

An intelligent, voice-first shopping assistant powered by **FastAPI**, **React**, **Groq LLM**, **Qdrant Vector Cloud**, **MiniLM Embeddings**, and **Supabase PostgreSQL**.

---

## 🌟 Overview

The **Voice Shopping Assistant** allows users to build and manage personal shopping lists using natural language voice commands. The system features:

- **Continuous Voice Listening**: Real-time microphone listening via Web Speech API.
- **Smart Assistant Voice (TTS)**: Spoken audio feedback via SpeechSynthesis with a dedicated **Assistant Voice ON/OFF** toggle, stale closure prevention, and instant cancellation.
- **LLM Entity Extraction**: Groq NLU (`openai/gpt-oss-20b` / `llama-3.3-70b-versatile`) with deterministic rule-based fallback parser.
- **5-Rule Size Decision Engine**: Solves size selection deterministically using catalog availability and historical purchase preferences ($\ge 2/3$ frequency rule).
- **Expanded Indian Supermarket Catalogue**: 114+ everyday products across 16 categories with size variants.
- **Co-Purchase Recommendation Engine**: Mines the user's last 3 completed shopping lists to suggest complementary items.
- **Customer Authentication & IDOR Protection**: JWT Bearer authentication with personal shopping list data isolation.
- **Semantic Product Search**: Dense 384-dimensional vector retrieval using MiniLM `all-MiniLM-L6-v2` and Qdrant Cloud.

---

## 🏗️ System Architecture

```
                                    User Voice / UI
                                          │
                        ┌─────────────────┴─────────────────┐
                        ▼                                   ▼
              SpeechRecognition (STT)              SpeechSynthesis (TTS)
                        │                                   ▲
                        ▼                                   │
                React Frontend ────────── JWT Token ────────┼─── (Voice Toggle)
                        │                                   │
                        ▼ (HTTP REST API)                   │
                FastAPI Backend ────────────────────────────┘
                        │
      ┌─────────────────┼─────────────────┬─────────────────┐
      ▼                 ▼                 ▼                 ▼
   Groq LLM       Size Decision       Co-Purchase       Qdrant Vector
   (NLU Parsing)     Engine          Engine & DB         (MiniLM Search)
                        │                 │
                        └────────┬────────┘
                                 ▼
                    Supabase / PostgreSQL DB
```

---

## 🧰 Tech Stack

| Component | Technology |
|---|---|
| **Frontend** | React 19, Vite, Tailwind CSS, Web Speech API, SpeechSynthesis API, Lucide Icons, Axios |
| **Backend** | Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy, Uvicorn, Pytest |
| **Database** | Supabase PostgreSQL (Production) / SQLite (Local Development) |
| **Authentication** | Bearer JWT (PBKDF2-HMAC-SHA256 password hashing) |
| **Vector Store** | Qdrant Cloud (`sentence-transformers` / `all-MiniLM-L6-v2`) |
| **LLM & NLU** | Groq API (`openai/gpt-oss-20b` or `llama-3.3-70b-versatile`) |

---

## 📁 Repository Structure

```text
├── backend/
│   ├── app/
│   │   ├── ai/            # Groq LLM integration & Rule NLP fallback
│   │   ├── api/           # Auth, Commands, Shopping, Products, Suggestions routes
│   │   ├── core/          # Security (JWT, Password hashing) & Config settings
│   │   ├── database/      # SQLAlchemy ORM models & database migrations
│   │   ├── recommendations/# Co-Purchase recommendation engine
│   │   ├── schemas/       # Pydantic data schemas
│   │   ├── search/        # Qdrant & MiniLM vector search service
│   │   └── services/      # Size decision engine & shopping business logic
│   ├── tests/             # Automated test suite (339 test cases)
│   ├── .env.example       # Backend environment variables template
│   ├── main.py            # FastAPI entrypoint
│   └── requirements.txt   # Backend Python dependencies
├── frontend/
│   ├── src/
│   │   ├── components/    # VoiceToggle, ShoppingList, Login, Signup, SmartSuggestions
│   │   ├── context/       # AuthContext provider
│   │   └── services/      # Axios API service
│   ├── .env.example       # Frontend environment variables template
│   └── package.json       # Frontend Node dependencies
├── scripts/
│   └── import_products.py # Supermarket catalogue import & Qdrant embedding script
├── .gitignore             # Git exclusion rules
├── .env.example           # Root environment variable template
├── requirements.txt       # Root Python dependencies for cloud deployment
└── README.md
```


## 🚀 Local Development Setup

### 1. Prerequisites
- Python 3.11+
- Node.js 18+ & npm
- Conda or virtualenv (recommended)

### 2. Backend Setup
```bash
# Clone the repository
git clone https://github.com/your-username/voice-shopping-assistant.git
cd voice-shopping-assistant

# Create & activate virtual environment
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install backend dependencies
pip install -r requirements.txt

# Seed product catalogue database & generate MiniLM vectors
python scripts/import_products.py

# Start FastAPI backend server
uvicorn backend.app.main:app --reload --port 8000
```
Interactive API documentation is available at `http://localhost:8000/api/docs`.

### 3. Frontend Setup
```bash
cd frontend

# Install Node dependencies
npm install

# Start Vite development server
npm run dev
```
Open `http://localhost:5173` in Google Chrome or Microsoft Edge for Web Speech API support.

### 4. Run Automated Tests
```bash
python -m pytest backend/tests/ -v
```

---

## ☁️ Free Cloud Deployment Guide

### 1. Backend Deployment on Render
1. Create a free account on [Render.com](https://render.com/).
2. Click **New +** $\rightarrow$ **Web Service** and connect your GitHub repository.
3. Set the following settings:
   - **Root Directory**: `.` (or leave empty)
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT`
4. In **Environment Variables**, add:
   - `GROQ_API_KEY`
   - `GROQ_MODEL`
   - `DATABASE_URL` (your Supabase PostgreSQL URL)
   - `QDRANT_URL`
   - `QDRANT_API_KEY`
   - `SECRET_KEY`
   - `FRONTEND_URL` (your Vercel URL)
5. Deploy Web Service. Render will expose your backend at `https://your-app.onrender.com`.

### 2. Frontend Deployment on Vercel
1. Create a free account on [Vercel.com](https://vercel.com/).
2. Import your GitHub repository into Vercel.
3. Set the **Framework Preset** to **Vite**.
4. Set the **Root Directory** to `frontend`.
5. Under **Environment Variables**, add:
   - `VITE_API_BASE_URL`: `https://your-app.onrender.com`
6. Click **Deploy**. Vercel will host your app at `https://your-app.vercel.app`.

### 3. Database Deployment on Supabase
1. Create a project at [Supabase.com](https://supabase.com/).
2. Under **Project Settings** $\rightarrow$ **Database**, copy your PostgreSQL Connection String (`URI`).
3. Set `DATABASE_URL` in your Render backend environment settings. FastAPI will automatically run migrations and create all tables on startup.

---

## 🔐 Security & Data Isolation
- **No Hardcoded Secrets**: All API keys, connection strings, and tokens are configured via environment variables.
- **Server-Derived Identity**: Identity is extracted exclusively from validated Bearer JWT tokens. Frontend-supplied user IDs are ignored.
- **IDOR Protection**: Shopping lists, items, and purchase histories are restricted to `WHERE user_id = authenticated_user.id`.

---

## 📄 License & Notes
Designed for production-grade demonstration of clean separation between LLM intent extraction, deterministic size engines, vector similarity search, and real-time Web Speech UI.
