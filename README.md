# 🛒 ShopVA — Voice Shopping Assistant

### AI-Powered Voice-First Shopping List Manager

ShopVA is an intelligent voice-first shopping assistant that allows customers to create and manage personalized shopping lists using natural language voice commands.

It combines **React, FastAPI, Groq LLM, Qdrant Cloud, MiniLM embeddings, and Supabase PostgreSQL** to provide voice interaction, catalogue-aware shopping, semantic product search, personalized suggestions, and secure customer-specific shopping lists.

---

## 🚀 Live Application

### Frontend

**https://shop-va-shopping-voice-assistant.vercel.app/**

---

## 🌟 Key Features

### 🎙️ Voice Shopping

Users can manage their shopping list using natural voice commands.

Examples:

- "Add milk"
- "Buy 2 packets of biscuits"
- "I need 500 grams of honey"
- "Remove bread"
- "Update the quantity of rice"

The assistant supports:

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

Intent: ADD_ITEM
Product: Biscuits
Quantity: 2
Unit: Packet

The system can understand different natural-language expressions for the same operation.

Examples:

"Add milk"
"Buy milk"
"I need milk"
"Include milk in my list"
"Put milk on my shopping list"

These can all be interpreted as an ADD_ITEM operation.

A deterministic rule-based fallback parser is also available when LLM parsing is unavailable.

🛍️ Catalogue-Aware Shopping

The supermarket catalogue is the source of truth for products that can be added to the shopping list.

The system follows this workflow:

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

Only products available in the supermarket catalogue can be added.

Example

If the customer says:

"Add medicine"

and Medicine is not available in the supermarket catalogue, the system rejects the request instead of adding an arbitrary product name.

The assistant responds appropriately without creating an invalid shopping-list item.

This prevents unknown or hallucinated products from entering the shopping list.

Catalogue Validation Principle

The LLM is responsible for understanding what the customer said.

The catalogue is responsible for determining whether the product actually exists.

LLM
 ↓
"What product did the customer request?"

        ↓

Catalogue
 ↓
"Does this product exist?"

        ↓

YES → Continue
NO  → Reject request
📦 Intelligent Size & Quantity Management

ShopVA separates:

Product
Quantity
Unit
Package size

This separation prevents incorrect quantity and size conversions.

For example:

"Add 500g honey"

must remain:

Product: Honey
Quantity: 1
Size: 500g

and must not become:

Size: 5g
Size Selection

If the customer specifies a size:

"Add 500g honey"

the requested size is preserved and checked against the catalogue.

If the customer does not specify a size:

"Add shampoo"

the system:

Checks the available catalogue sizes.
Checks the customer's recent purchase history.
Looks at the customer's previous purchasing pattern.
Uses a suitable previously purchased size when the defined history rule is satisfied.
Otherwise asks the customer to choose from the available sizes.

The size-selection process is deterministic and does not allow the LLM to invent catalogue sizes.

🤖 Smart Suggestions

ShopVA provides personalized recommendations using the customer's shopping history.

Co-Purchase Recommendations

The system analyzes the customer's last 3 completed shopping lists to identify products that are frequently purchased together.

For example:

List 1:
Bread + Jam

List 2:
Bread + Jam

List 3:
Bread + Milk

When the customer adds:

Bread

the system can suggest:

Jam

because Jam appeared together with Bread in multiple recent shopping lists.

The recommendations are based on the individual customer's purchase history rather than a global shopping list.

🔎 Semantic Product Search

ShopVA uses vector similarity search to understand product queries that may not exactly match catalogue names.

Technologies
Qdrant Cloud
Dense vector search
sentence-transformers/all-MiniLM-L6-v2
384-dimensional embeddings

Example:

Customer Query
      ↓
Semantic Search
      ↓
Relevant Catalogue Candidates
      ↓
Catalogue Validation
      ↓
Valid Product

Semantic search is used to retrieve relevant catalogue candidates.

However, a semantic-search result is not automatically considered a valid product.

The backend validates the resolved product against the actual supermarket catalogue before adding it to the shopping list.

This prevents semantic-search false positives and hallucinated products.

🗂️ Product Categories

The supermarket catalogue contains products organized into categories such as:

Dairy
Fruits
Vegetables
Bakery
Snacks
Beverages
Staples
Personal Care
Household
Frozen Foods
Condiments
Breakfast
And more

The shopping list provides an:

According to category

toggle.

When enabled, products are organized according to their catalogue category.

This makes large shopping lists easier to navigate.

👤 Customer Accounts & Data Isolation

ShopVA supports individual customer accounts.

Each customer has their own:

Shopping list
Shopping items
Purchase history
Shopping suggestions

The application provides:

Sign Up
Login
JWT authentication
Secure password hashing
Customer-specific shopping lists
Customer-specific purchase history
IDOR protection
Server-side identity validation

A customer cannot access another customer's shopping data.

The backend derives the authenticated customer from the validated JWT rather than trusting a customer ID supplied by the frontend.

🎧 Voice Interaction Controls
Continuous Voice Listening

The application provides a dedicated voice-listening toggle.

When enabled:

Voice Listening = ON
        ↓
Continuously listen for commands
        ↓
Process customer commands

The assistant continues listening until the customer manually turns the listening mode off.

Assistant Voice

The application also provides a separate Assistant Voice toggle.

This controls whether the assistant speaks its responses using text-to-speech.

The two controls are independent:

Voice Listening
       ≠
Assistant Voice

Therefore:

Listening can be ON while Assistant Voice is OFF.
Assistant Voice can be disabled without disabling command recognition.

The application also prevents assistant-generated speech from being interpreted as a new customer command.

🖥️ User Interface

The application provides a simple shopping-focused interface.

Main UI Features
Voice command interface
Shopping list
Manual item entry
Quantity controls
Product size handling
Category sorting
Smart suggestions
Catalogue validation
Purchase completion
Login
Signup
Real-time command feedback
Voice listening controls
Assistant voice controls

The interface is designed around a minimal and straightforward shopping workflow.

🏗️ System Architecture
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
🔄 Request Processing Architecture

ShopVA separates AI interpretation from deterministic application logic.

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
🧰 Technology Stack
Component	Technology
Frontend	React 19, Vite, Tailwind CSS
Voice Input	Web Speech API
Voice Output	SpeechSynthesis API
Icons	Lucide Icons
HTTP Client	Axios
Backend	Python 3.11+, FastAPI
Validation	Pydantic v2
ORM	SQLAlchemy
Server	Uvicorn
Testing	Pytest
Database	Supabase PostgreSQL
Authentication	JWT Bearer Authentication
Password Security	PBKDF2-HMAC-SHA256
LLM / NLU	Groq API
Vector Database	Qdrant Cloud
Embeddings	sentence-transformers/all-MiniLM-L6-v2
Hosting	Vercel + Render + Cloud Services
📁 Repository Structure
ShopVA-Shopping-Voice-Assistant/
│
├── backend/
│   ├── app/
│   │   ├── ai/
│   │   │   └── Groq LLM and NLP fallback
│   │   ├── api/
│   │   │   └── Authentication, Commands,
│   │   │       Shopping, Products and Suggestions
│   │   ├── core/
│   │   │   └── Security and configuration
│   │   ├── database/
│   │   │   └── SQLAlchemy models and database logic
│   │   ├── recommendations/
│   │   │   └── Co-purchase recommendation engine
│   │   ├── schemas/
│   │   │   └── Pydantic schemas
│   │   ├── search/
│   │   │   └── Qdrant and semantic search services
│   │   └── services/
│   │       └── Shopping and size decision logic
│   ├── tests/
│   ├── .env.example
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── context/
│   │   └── services/
│   ├── .env.example
│   └── package.json
│
├── scripts/
│   └── import_products.py
│
├── .gitignore
├── .env.example
├── requirements.txt
└── README.md
🔐 Security & Data Isolation

ShopVA follows a security-focused architecture.

No Hardcoded Secrets

API keys, database credentials, JWT secrets, and other sensitive configuration are supplied through environment variables.

Sensitive credentials are not committed to the public repository.

Server-Derived Identity

Customer identity is derived from the validated JWT token.

The backend does not trust a customer ID supplied directly by the frontend.

IDOR Protection

Shopping lists, shopping items, and purchase history are restricted to the authenticated customer.

Catalogue Validation

Products must be validated against the supermarket catalogue before they can be added.

The LLM cannot directly create arbitrary catalogue products.

Semantic Search Validation

Qdrant results are treated as candidate results.

The backend validates the corresponding catalogue product before accepting the item.

🧠 AI + Deterministic Business Logic

A key design principle of ShopVA is separating language understanding from business decisions.

LLM Responsibilities

The LLM understands what the customer is asking.

For example:

"Can you put two bottles of shampoo on my list?"

        ↓

Intent: ADD_ITEM
Product: Shampoo
Quantity: 2
Unit: Bottle
Backend Responsibilities

The backend determines:

Whether the product exists.
Whether the product is available.
Which category it belongs to.
Which sizes are available.
Whether the requested size is valid.
Whether previous purchase history should influence size selection.
Whether the item can be added.
Which recommendations should be generated.

This prevents the LLM from inventing:

Products
Sizes
Categories
Catalogue availability
📊 End-to-End Shopping Workflow
Customer Voice Command
          │
          ▼
Speech Recognition
          │
          ▼
LLM Intent & Entity Extraction
          │
          ▼
Product Resolution
          │
          ▼
Semantic Catalogue Search
          │
          ▼
Catalogue Validation
          │
          ▼
Quantity & Size Processing
          │
          ▼
Purchase History Analysis
          │
          ▼
Shopping List Update
          │
          ▼
Smart Suggestions
          │
          ▼
Voice Confirmation
🧪 Reliability & Error Handling

The application is designed to handle common AI, voice, database, and catalogue failures.

Examples include:

Unknown products
Products not present in the catalogue
Unsupported product sizes
Missing quantities
Invalid commands
LLM API failures
Voice recognition failures
Authentication failures
Database connection failures
Semantic search failures
Invalid catalogue matches

The backend validates AI output before performing shopping-list operations.

🛡️ Example Catalogue Validation

Consider the command:

"Add medicine"

The LLM may correctly understand:

Intent: ADD_ITEM
Product: Medicine

However, the backend then checks:

Does "Medicine" exist in the supermarket catalogue?
If YES
Catalogue Product Found
        ↓
Validate Size
        ↓
Validate Quantity
        ↓
Add to Shopping List
If NO
Catalogue Product Not Found
        ↓
Reject Request
        ↓
Do NOT create ShoppingListItem
        ↓
Inform Customer

This ensures that an arbitrary product name cannot be inserted into the shopping list simply because the LLM recognized it.

📏 Example Size Handling
User specifies size
"Add 500g honey"

Expected interpretation:

Product  = Honey
Quantity = 1
Size     = 500g

The system checks whether the requested size exists in the catalogue.

User does not specify size
"Add honey"

The system:

Honey
  ↓
Check catalogue sizes
  ↓
Check recent purchase history
  ↓
Previous suitable size?
  ├── YES → Use it
  │
  └── NO → Ask customer to select size

The assistant never speaks internal placeholders such as:

_
____
______

Missing values are represented semantically and the customer is given a proper size-selection option.

🤖 Example Smart Suggestion

Suppose the customer's completed lists are:

Shopping List 1:
Bread
Jam
Milk

Shopping List 2:
Bread
Jam
Butter

Shopping List 3:
Bread
Jam
Eggs

The system detects:

Bread + Jam

as a repeated co-purchase relationship.

When the customer adds:

Bread

the assistant can suggest:

You frequently buy Jam with Bread.
Would you like to add Jam?

The recommendation is based on the customer's own purchase history.

🎯 Project Highlights
🎙️ Voice-first shopping interaction
🧠 LLM-based natural language understanding
🔎 Semantic product retrieval
🛍️ Catalogue-grounded product validation
📦 Deterministic size decision engine
🤖 Personalized co-purchase recommendations
👤 Secure customer-specific shopping lists
🔐 JWT authentication
🛡️ IDOR protection
🗂️ Category-based shopping list organization
🎧 Continuous voice interaction
🔊 Independent assistant voice control
☁️ Cloud-hosted architecture
🧪 Automated backend testing
🔒 Environment-based secret management
🌐 Deployment

The production frontend is hosted at:

https://shop-va-shopping-voice-assistant.vercel.app/

The application uses cloud-hosted backend, database, vector-search, and AI services.

Sensitive service credentials are managed through deployment environment variables rather than being stored in the repository.

🎯 Design Philosophy

ShopVA combines modern AI capabilities with deterministic software engineering.

The application does not rely entirely on an LLM for business decisions.

Instead:

LLM
  ↓
Understand the customer's language

Catalogue
  ↓
Confirm that the product exists

Backend
  ↓
Validate the request

Business Logic
  ↓
Determine quantity, size and recommendations

Database
  ↓
Persist customer-specific data

This architecture improves reliability, reduces hallucinated catalogue products, and keeps customer data isolated.

📄 License

This project was developed as a software engineering technical assessment and demonstration of an AI-powered voice shopping application.
