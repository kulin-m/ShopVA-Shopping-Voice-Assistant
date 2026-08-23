# 🛒 ShopVA — Voice Shopping Assistant

> **AI-Powered Voice-First Shopping List Manager**

ShopVA is an intelligent voice-first shopping assistant that allows customers to create and manage personalized shopping lists using natural language voice commands.

It combines **React**, **FastAPI**, **Groq LLM**, **Qdrant Cloud**, **MiniLM embeddings**, and **Supabase PostgreSQL** to provide voice interaction, catalogue-aware shopping, semantic product search, personalized suggestions, and secure customer-specific shopping lists.

---

## 🚀 Live Application

- **Frontend:** [https://shop-va-shopping-voice-assistant.vercel.app/](https://shop-va-shopping-voice-assistant.vercel.app/)

---

## 🌟 Key Features

### 🎙️ Voice Shopping

Users can manage their shopping list using natural voice commands.

**Examples:**
- *"Add milk"*
- *"Buy 2 packets of biscuits"*
- *"I need 500 grams of honey"*
- *"Remove bread"*
- *"Update the quantity of rice"*

**Core Capabilities:**
- Add items
- Remove items
- Update quantities
- Natural-language commands
- Continuous voice listening
- Assistant Voice ON/OFF control
- Real-time command feedback

---

## 🧠 Natural Language Understanding

ShopVA uses a Groq-powered Large Language Model to understand the customer's natural language and identify the requested task.

For example:

```text
"Please buy two packets of biscuits"
                ↓
Intent:   ADD_ITEM
Product:  Biscuits
Quantity: 2
Unit:     Packet
```

The system can understand different natural-language expressions for the same operation:
- *"Add milk"*
- *"Buy milk"*
- *"I need milk"*
- *"Include milk in my list"*
- *"Put milk on my shopping list"*

All map directly to an `ADD_ITEM` operation.

> **Fallback:** A deterministic rule-based fallback parser is automatically engaged when LLM parsing is unavailable.

---

## 🛍️ Catalogue-Aware Shopping

The supermarket catalogue is the source of truth for products that can be added to the shopping list.

### Processing Workflow

```text
Voice Command
      ↓
LLM Intent & Entity Extraction
      ↓
Product Resolution
      ↓
Catalogue Search
      ↓
Catalogue Validation
      ↓
Size / Quantity Validation
      ↓
Add to Shopping List
```

Only products available in the supermarket catalogue can be added.

### Example Rejection

If the customer says:
> *"Add medicine"*

and **Medicine** is not available in the supermarket catalogue, the system rejects the request instead of adding an arbitrary product name. The assistant responds appropriately without creating an invalid shopping-list item, preventing unknown or hallucinated products from entering the database.

### Catalogue Validation Principle

- **LLM:** Responsible for understanding what the customer said.
- **Catalogue:** Responsible for determining whether the product actually exists.

```text
LLM:       "What product did the customer request?"
                         ↓
Catalogue: "Does this product exist?"
                         ↓
             YES → Continue
             NO  → Reject request
```

---

## 📦 Intelligent Size & Quantity Management

ShopVA explicitly separates:
- **Product**
- **Quantity**
- **Unit**
- **Package size**

This separation prevents incorrect quantity and size conversions.

**Example:**
- Command: *"Add 500g honey"*
- **Correct Interpretation:** `Product: Honey`, `Quantity: 1`, `Size: 500g`
- **Avoided Bug:** `Size: 5g`

### Size Selection Rules

- **User specifies size** (*"Add 500g honey"*): The requested size is preserved and checked against catalogue inventory.
- **User does not specify size** (*"Add shampoo"*):
  1. Checks available catalogue sizes.
  2. Checks customer recent purchase history.
  3. Uses a suitable previously purchased size if matching criteria are met.
  4. Otherwise, prompts the customer to choose from available catalogue sizes.

The size-selection process is deterministic and does not permit the LLM to invent catalogue sizes.

---

## 🤖 Smart Suggestions

ShopVA provides personalized recommendations using the customer's shopping history.

### Co-Purchase Recommendations

The system analyzes the customer's last 3 completed shopping lists to identify products frequently purchased together.

```text
List 1: Bread + Jam
List 2: Bread + Jam
List 3: Bread + Milk
```

When the customer adds **Bread**, the system suggests **Jam** based on their individual co-purchase frequency rather than a global list.

---

## 🔎 Semantic Product Search

ShopVA uses vector similarity search to resolve product queries that do not match catalogue names verbatim.

### Tech Stack for Search
- **Vector Database:** Qdrant Cloud
- **Search Type:** Dense vector search
- **Model:** `sentence-transformers/all-MiniLM-L6-v2` (384-dimensional embeddings)

```text
Customer Query 
      ↓ 
Semantic Search 
      ↓ 
Relevant Catalogue Candidates 
      ↓ 
Catalogue Validation 
      ↓ 
Valid Product
```

> **Note:** Semantic search outputs are strictly treated as candidates. The backend validates resolved items against the active relational catalogue before mutating the list to eliminate false positives.

---

## 🗂️ Product Categories

Products are categorized into:
- Dairy
- Fruits & Vegetables
- Bakery & Snacks
- Beverages
- Staples
- Personal Care & Household
- Frozen Foods & Condiments

The UI features an **"According to category"** toggle to organize large shopping lists into structured groups.

---

## 👤 Customer Accounts & Data Isolation

ShopVA supports multi-tenant customer accounts:
- Independent shopping lists and items
- Customer-specific purchase history and suggestions
- Sign Up & Login with secure password hashing (PBKDF2-HMAC-SHA256)
- JWT bearer authentication with server-side identity derivation
- Built-in Insecure Direct Object Reference (IDOR) protection

---

## 🎧 Voice Interaction Controls

- **Continuous Voice Listening:** Toggles persistent background command listening until manually stopped.
- **Assistant Voice (TTS):** Independent control to enable/disable spoken responses.
- **Echo Prevention:** Prevents assistant text-to-speech output from looping into speech recognition as new input.

---

## 🖥️ User Interface Features

- Voice command interface with real-time visual feedback
- Shopping list with manual entry and item quantity steppers
- Product size modal selectors
- Category grouping view
- Personalized recommendation prompts
- Authentication (Sign up / Login) screens

---

## 🏗️ System Architecture

```text
                         Customer
                            │
                ┌───────────┴───────────┐
                │                       │
          Voice Input                UI Input
                │                       │
                ▼                       ▼
       Speech Recognition          React Frontend
                │                       │
                └───────────┬───────────┘
                            │
                            ▼
                    FastAPI Backend
                            │
       ┌────────────────────┼────────────────────┐
       │                    │                    │
       ▼                    ▼                    ▼
    Groq LLM          Catalogue Engine      Suggestions
       │                    │                    │
       │              ┌─────┴─────┐              │
       │              │           │              │
       │              ▼           ▼              │
       │        PostgreSQL     Qdrant             │
       │                      + MiniLM            │
       │                                           │
       └───────────────────┬───────────────────────┘
                           │
                           ▼
                    Shopping List
                           │
                           ▼
                    Voice Response
```

---

## 🔄 Request Processing Architecture

```text
Customer Voice Command
          │
          ▼
Speech Recognition
          │
          ▼
LLM / NLP Layer
          │
          ▼
Intent + Product + Quantity + Size
          │
          ▼
Catalogue Resolver
          │
          ├───────────────┐
          ▼               ▼
   PostgreSQL          Qdrant
   Catalogue         Semantic Search
          │               │
          └───────┬───────┘
                  ▼
          Catalogue Validation
                  │
          ▼
       Quantity / Size Engine
                  │
          ▼
       Purchase History
                  │
          ▼
        Shopping List
                  │
          ▼
        Suggestions
                  │
          ▼
        Voice Response
```

---

## 🧰 Technology Stack

| Layer | Technology |
| :--- | :--- |
| **Frontend** | React 19, Vite, Tailwind CSS |
| **Voice Input** | Web Speech API |
| **Voice Output** | SpeechSynthesis API |
| **Icons & UI** | Lucide Icons, Axios |
| **Backend Framework** | Python 3.11+, FastAPI, Uvicorn |
| **Validation & ORM** | Pydantic v2, SQLAlchemy |
| **Database** | Supabase PostgreSQL |
| **Security & Auth** | JWT Bearer Authentication, PBKDF2-HMAC-SHA256 |
| **LLM / NLU** | Groq API |
| **Vector Search** | Qdrant Cloud |
| **Embeddings** | `sentence-transformers/all-MiniLM-L6-v2` |
| **Testing & Hosting** | Pytest, Vercel, Render |

---

## 📁 Repository Structure

```text
ShopVA-Shopping-Voice-Assistant/
│
├── backend/
│   ├── app/
│   │   ├── ai/              # Groq LLM and NLP fallback
│   │   ├── api/             # Authentication, Commands, Shopping, Products, Suggestions
│   │   ├── core/            # Security and configuration
│   │   ├── database/        # SQLAlchemy models and database sessions
│   │   ├── recommendations/ # Co-purchase recommendation engine
│   │   ├── schemas/         # Pydantic request/response schemas
│   │   ├── search/          # Qdrant and semantic search services
│   │   └── services/        # Shopping and size decision logic
│   ├── tests/               # Pytest suite
│   ├── .env.example
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── components/      # UI, voice, and list components
│   │   ├── context/         # Auth and state management
│   │   └── services/        # API and Speech API wrappers
│   ├── .env.example
│   └── package.json
│
├── scripts/
│   └── import_products.py   # Catalogue bulk import script
│
├── .gitignore
├── .env.example
├── requirements.txt
└── README.md
```

---

## 🔐 Security & Data Isolation

- **No Hardcoded Secrets:** Credentials, JWT keys, and API tokens are managed via environment variables.
- **Server-Derived Identity:** Customer identity is resolved strictly via validated JWT payloads, mitigating IDOR vulnerabilities.
- **Catalogue Boundary Enforcement:** Prevents arbitrary client-injected product names from writing to user lists.

---

## 🧠 AI + Deterministic Business Logic

| Component | Responsibility |
| :--- | :--- |
| **LLM** | Extracts intent, product candidate, quantity, and requested units from natural language. |
| **Backend Logic** | Confirms availability, enforces sizes, queries purchase history, and handles suggestions. |

---

## 🛡️ Validation & Size Decision Flows

### Catalogue Validation Flow

```text
Command: "Add medicine"
                ↓
    Intent: ADD_ITEM | Product: Medicine
                ↓
    Does "Medicine" exist in catalogue?
         ├── YES → Validate Size & Quantity → Add Item
         └── NO  → Reject Request → Notify Customer
```

### Deterministic Size Decision Flow

```text
Command: "Add honey" (Unspecified Size)
                ↓
    Query Catalogue for Available Sizes
                ↓
    Check User Recent Purchase History
                ↓
    Found matching past purchase?
         ├── YES → Apply standard past size
         └── NO  → Prompt customer to select variant
```

---

## 🎯 Project Highlights

- 🎙️ Voice-first shopping interaction
- 🧠 LLM-based natural language understanding
- 🔎 Semantic product retrieval with Qdrant
- 🛍️ Catalogue-grounded product validation
- 📦 Deterministic size decision engine
- 🤖 Personalized co-purchase recommendations
- 👤 Secure customer data isolation & JWT authentication
- 🗂️ Category-based organization
- ☁️ Cloud-hosted serverless architecture

---

## 📄 License

This project was developed as a software engineering technical assessment and demonstration of an AI-powered voice shopping application.
