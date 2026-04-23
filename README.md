# 🚀 RAG Knowledge Engine

<p align="center">
  <b>Powerful Retrieval-Augmented Generation (RAG) System</b><br>
  Built with FastAPI, PostgreSQL, and Qdrant
</p>

<p align="center">
  <a href="https://github.com/AbdElrhmanmwadi">
    <img src="https://img.shields.io/badge/GitHub-AbdElrhmanmwadi-black?logo=github">
  </a>
  <img src="https://img.shields.io/badge/Python-3.10+-blue?logo=python">
  <img src="https://img.shields.io/badge/FastAPI-Backend-green?logo=fastapi">
  <img src="https://img.shields.io/badge/License-MIT-yellow">
</p>

---

## 🌍 Overview | نظرة عامة

### 🇺🇸 English

RAG Knowledge Engine is a scalable backend system that enables:

* 📂 Uploading documents
* ✂️ Intelligent text chunking
* 🧠 Embedding generation using LLMs
* 🔍 Semantic search via Vector DB
* 🤖 AI-powered answer generation

### 🇸🇦 عربي

نظام ذكي يعتمد على RAG ويتيح:

* رفع الملفات 📂
* تقسيم النصوص ✂️
* توليد Embeddings 🧠
* البحث الذكي 🔍
* توليد الإجابات بالذكاء الاصطناعي 🤖

---

## 🧠 What is RAG?

RAG = Retrieval + Generation

```text id="v8c3r1"
User Query
   ↓
Embedding
   ↓
Vector Search (Qdrant)
   ↓
Relevant Context
   ↓
LLM (Cohere / OpenAI)
   ↓
Final Answer
```

---

## 🛠️ Tech Stack

* ⚡ FastAPI
* 🐍 Python
* 🧠 RAG Architecture
* 🗄️ PostgreSQL + pgvector
* 📦 Qdrant Vector Database
* 🤖 Cohere / OpenAI

---

## 🏗️ Architecture

```text id="9u6n2a"
FastAPI
 ├── Routes
 ├── Controllers
 ├── Models
 └── Services
      ├── LLM Providers
      └── Vector DB

Databases:
- PostgreSQL (structured data)
- Qdrant (vector embeddings)
```

---

## 🔄 Workflow

### 1. Upload File

* Save file locally
* Store metadata in PostgreSQL

### 2. Process File

* Extract text
* Split into chunks
* Store chunks

### 3. Index Data

* Generate embeddings
* Store in Qdrant

### 4. Query

* Semantic search
* AI answer generation

---

## 📂 Project Structure

```bash id="j9zq7w"
project/
│
├── app/
│   ├── api/
│   ├── controllers/
│   ├── models/
│   └── services/
│
├── llm/
│   ├── template/
│   │   ├── local/
│   │   │   ├── ar/
│   │   │   │   └── rag.py
│   │   │   └── en/
│   │   │       └── rag.py
│
├── assets/
├── tests/
├── .env
└── README.md
```

---

## ⚙️ Installation

```bash id="2k4p9m"
git clone https://github.com/AbdElrhmanmwadi/rag-knowledge-engine.git
cd rag-knowledge-engine

python -m venv venv
source venv/bin/activate   # Linux / Mac
venv\Scripts\activate      # Windows

pip install -r requirements.txt
```

---

## ▶️ Run

```bash id="m3r7lp"
uvicorn app.main:app --reload
```

📍 Open:
http://127.0.0.1:8000/docs

---

## 🔐 Environment Variables

```env id="p0n8rf"
POSTGRES_USERNAME=postgres
POSTGRES_PASSWORD=yourpassword
POSTGRES_DB=rag_db

COHERE_API_KEY=your_key
OPENAI_API_KEY=your_key

VECTOR_DB_BACKEND=QDRANT
```

---

## 📡 API Endpoints

| Method | Endpoint                            | Description     |
| ------ | ----------------------------------- | --------------- |
| POST   | /api/v1/data/upload/{project_id}    | Upload file     |
| POST   | /api/v1/data/process/{project_id}   | Process file    |
| POST   | /api/v1/nlp/index/push/{project_id} | Index data      |
| GET    | /api/v1/nlp/index/info/{project_id} | Collection info |

---

## 🚀 Roadmap

* 🔥 Improve performance (batch embeddings)
* 🔥 Add authentication (JWT)
* 🔥 Deploy to cloud

---

## 👨‍💻 Author

**Abd elrahman Ahmed wadi**
🔗 https://github.com/AbdElrhmanmwadi

