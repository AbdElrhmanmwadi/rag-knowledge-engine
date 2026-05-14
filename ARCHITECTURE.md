# RAG Knowledge Engine - Architecture & Data Models

## System Architecture

### Application Stack
```
┌─────────────────────────────────────────────────────────┐
│              FastAPI Application                         │
│              (uvicorn server on :8000)                   │
│                                                          │
│  ┌───────────────────────────────────────────────────┐  │
│  │  Routes Layer                                      │  │
│  │  ├─ base_router     (/api/v1)                    │  │
│  │  ├─ data_router     (/api/v1/data)               │  │
│  │  └─ nlp_router      (/api/v1/nlp)                │  │
│  └───────────────────────────────────────────────────┘  │
│                        ↓                                 │
│  ┌───────────────────────────────────────────────────┐  │
│  │  Controllers Layer (Business Logic)                │  │
│  │  ├─ DataController                               │  │
│  │  ├─ ProcessController                            │  │
│  │  ├─ NLPController                                │  │
│  │  ├─ ProjectController                            │  │
│  │  └─ BaseController                               │  │
│  └───────────────────────────────────────────────────┘  │
│                 ↙              ↓              ↖          │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐ │
│  │ Models Layer │  │ Stores Layer │  │ Helpers Layer │ │
│  │              │  │              │  │               │ │
│  │ ProjectModel │  │ LLM Providers│  │ config.py     │ │
│  │ ChunkModel   │  │ - OpenAI     │  │               │ │
│  │ AssetModel   │  │ - Cohere     │  │ get_settings()│ │
│  │              │  │              │  │               │ │
│  │ DB Schemes   │  │ VectorDB     │  └───────────────┘ │
│  │ - Project    │  │ - Qdrant     │                    │
│  │ - DataChunk  │  │ - Provider   │                    │
│  │ - Asset      │  │ - Factory    │                    │
│  └──────────────┘  └──────────────┘                    │
│         ↓                 ↙            ↖                │
└─────────────┼──────────────────────────┼─────────────┘
              ↓                          ↓
    ┌──────────────────────┐  ┌──────────────────────┐
    │  PostgreSQL          │  │  Qdrant VectorDB     │
    │  + pgvector          │  │  (Local on disk)     │
    │                      │  │                      │
    │  Tables:             │  │  Collections:        │
    │  - projects          │  │  - collection_N      │
    │  - chunks            │  │  - points/vectors    │
    │  - assets            │  │  - metadata payload  │
    │                      │  │                      │
    │  Indexes:            │  │  Distance: Cosine    │
    │  - project_id        │  │  Embedding: 384-dim  │
    │  - asset_id          │  │                      │
    └──────────────────────┘  └──────────────────────┘
             ↑                           ↑
             └────────────┬──────────────┘
                          │
              Docker Compose Services
              (mongo:7, pgvector:0.8.2)
```

---

## Request Flow

### 1. File Upload Flow
```
POST /api/v1/data/upload/123 + file.txt
    ↓
    Request → FastAPI → data_router → upload_data()
    ↓
    DataController.validate_uploaded_file()
        - Check MIME type: "text/plain" ✓
        - Check size: ≤ 10MB ✓
        - Return (True, "validated")
    ↓
    ProjectModel.get_project_or_create("123")
        - Query: SELECT * FROM projects WHERE project_id=123
        - If not exists: INSERT INTO projects (project_id=123)
        - Return Project object
    ↓
    DataController.generate_unique_file_Path()
        - Generate: "abc123def456_file.txt"
        - Path: assets/files/123/abc123def456_file.txt
    ↓
    Async file write to disk
        - Stream file chunks from upload
        - Write to filesystem
    ↓
    AssetModel.create_asset()
        - INSERT INTO assets:
            * asset_name: "abc123def456_file.txt"
            * asset_type: "FILE"
            * asset_size: bytes
            * asset_project_id: 123
    ↓
    Response:
    {
        "signal": "file_upload_success",
        "file_id": "abc123def456_file.txt"
    }
```

### 2. File Processing Flow
```
POST /api/v1/data/process/123 + {"chunk_size": 100, "overlap_size": 20}
    ↓
    ProjectModel.get_project_or_create("123")
    ↓
    Get all assets for project 123:
        SELECT * FROM assets WHERE asset_project_id=123
    ↓
    For each asset/file:
        ↓
        ProcessController.get_file_content(file_id)
            ├─ Determine file extension
            ├─ If .txt: TextLoader(file_path)
            ├─ If .pdf: TextLoader(file_path) ❌ WRONG! Should be PyMuPDFLoader
            └─ loader.load() → returns Document objects
        ↓
        ProcessController.process_file_content()
            ├─ Extract text from Document objects
            ├─ Create RecursiveCharacterTextSplitter
            ├─ Split with chunk_size=100, overlap=20
            └─ Returns list of Document chunks
        ↓
        For each chunk:
            CREATE DataChunk(
                chunk_text: chunk.page_content,
                chunk_metadata: chunk.metadata,
                chunk_order: position,
                chunk_project_id: 123,
                chunk_asset_id: asset_id
            )
        ↓
        ChunkModel.insert_many_chunks()
            └─ INSERT multiple chunks into chunks table
    ↓
    Response:
    {
        "signal": "file_process_success",
        "inserted_chunks": 250,
        "processed_files": 1
    }
```

### 3. Vector Indexing Flow
```
POST /api/v1/nlp/index/push/123
    ↓
    ChunkModel.get_chunks_by_project_id("123", page_number=1)
        ├─ Query: SELECT * FROM chunks WHERE chunk_project_id=123
        ├─ Limit: 10 per page
        └─ Returns: [Chunk1, Chunk2, ..., Chunk10]
    ↓
    NLPController.index_into_vectordb()
        ├─ Extract texts: [chunk.chunk_text for chunk in chunks]
        ├─ Extract metadata: [chunk.chunk_metadata for chunk in chunks]
        ↓
        For each text:
            ├─ embedding_client.embed_text(text)
            │   ├─ Call Cohere API: embed-multilingual-light-v3.0
            │   └─ Returns: vector [384-dimensional]
            ↓
            Create vectors = [vector1, vector2, ...]
        ↓
        QdrantDBProvider.create_collection(
            collection_name="collection_123",
            embedding_size=384,
            distance="cosine",
            do_reset=True (on first page)
        )
        ↓
        QdrantDBProvider.insert_many()
            ├─ Batch records into groups of 50
            ├─ For each batch:
            │   ├─ Create Record objects with:
            │   │  ├─ id: UUID
            │   │  ├─ vector: [384-dim embedding]
            │   │  └─ payload: {text, metadata}
            │   │
            │   └─ client.upload_records(collection_name, records)
            │       └─ Qdrant stores points in collection
            ↓
        Continue with page 2, 3, ... until no more chunks
    ↓
    Response:
    {
        "signal": "insert_into_vectordb_success"
    }
```

### 4. Missing: Query & Answer Generation Flow
```
❌ NOT IMPLEMENTED

Expected flow:
POST /api/v1/rag/query
    Body: {"project_id": 123, "query": "What is the strategy?"}
    ↓
    Embed query:
        embedding_client.embed_text(query)
        → vector [384-dim]
    ↓
    Search Qdrant:
        QdrantDBProvider.search_by_vector(
            collection_name="collection_123",
            vector=query_vector,
            limit=5
        )
        → Returns top-5 most similar chunks with scores
    ↓
    Retrieve contexts:
        contexts = [result.text for result in results]
    ↓
    Format prompt:
        prompt = f"""
        Context:
        {contexts}
        
        Question: {query}
        """
    ↓
    Generate answer:
        generation_client.generate_text(prompt)
        → Calls Cohere or OpenAI API
        → Returns answer text
    ↓
    Response:
    {
        "answer": "...",
        "sources": [results with citations]
    }
```

---

## Database Schema

### Table: projects
```sql
CREATE TABLE projects (
    project_id          INT PRIMARY KEY,
    project_uuid        UUID UNIQUE NOT NULL DEFAULT uuid_generate_v4(),
    created_at          TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP
);
```

**Purpose**: Track knowledge bases/projects  
**Relationships**: 1-to-many with chunks, 1-to-many with assets

### Table: chunks
```sql
CREATE TABLE chunks (
    chunk_id            INT PRIMARY KEY AUTOINCREMENT,
    chunk_uuid          UUID UNIQUE NOT NULL DEFAULT uuid_generate_v4(),
    chunk_text          VARCHAR NOT NULL,
    chunk_metadata      JSONB,
    chunk_order         INT NOT NULL,
    chunk_project_id    INT NOT NULL REFERENCES projects(project_id),
    chunk_asset_id      INT NOT NULL REFERENCES assets(asset_id),
    created_at          TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP
);

INDEX ix_chunk_project_id ON chunks(chunk_project_id);
INDEX ix_chunk_asset_id ON chunks(chunk_asset_id);
```

**Purpose**: Store document chunks  
**Example chunk_metadata**:
```json
{
    "source": "abc123_strategy.txt",
    "page": 1,
    "section": "Introduction",
    "line_start": 0,
    "line_end": 50
}
```

### Table: assets
```sql
CREATE TABLE assets (
    asset_id            INT PRIMARY KEY AUTOINCREMENT,
    asset_uuid          UUID UNIQUE NOT NULL DEFAULT uuid_generate_v4(),
    asset_type          VARCHAR NOT NULL,
    asset_name          VARCHAR NOT NULL,
    asset_size          INT NOT NULL,
    asset_config        JSONB,
    asset_project_id    INT NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
    created_at          TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP NOT NULL DEFAULT NOW()
);

INDEX ix_asset_project_id ON assets(asset_project_id);
INDEX ix_asset_type ON assets(asset_type);
```

**Purpose**: Track uploaded files  
**asset_type values**: "FILE"  
**Example**:
```json
{
    "asset_id": 42,
    "asset_type": "FILE",
    "asset_name": "abc123def456_strategy.txt",
    "asset_size": 15420,
    "asset_project_id": 123
}
```

---

## Vector Database Schema

### Qdrant Collection: collection_{project_id}

```
Collection: collection_123

Points: [
    {
        id: "550e8400-e29b-41d4-a716-446655440001",
        vector: [0.123, 0.456, ..., -0.789],  // 384 dimensions
        payload: {
            "text": "This is the strategy overview...",
            "metadata": {
                "source": "abc123_strategy.txt",
                "chunk_order": 1,
                "asset_id": 42
            }
        }
    },
    {
        id: "550e8400-e29b-41d4-a716-446655440002",
        vector: [0.234, 0.567, ..., -0.890],
        payload: {
            "text": "Implementation details of the strategy...",
            "metadata": {
                "source": "abc123_strategy.txt",
                "chunk_order": 2,
                "asset_id": 42
            }
        }
    },
    // ... more points
]

Config:
{
    distance_method: "cosine",  // or "dot"
    embedding_size: 384,         // for embed-multilingual-light-v3.0
    indexing_threshold: 0        // disable auto-indexing until optimization
}
```

**Vector Properties**:
- **Dimension**: 384 (for Cohere `embed-multilingual-light-v3.0`)
- **Distance Metric**: Cosine similarity (configurable to DOT)
- **Storage**: Local filesystem at `assets/database/qdrant_db/`

**Query Example**:
```python
# Search for chunks similar to user query
results = client.search(
    collection_name="collection_123",
    query_vector=[...384-dim vector...],
    limit=5
)

# Returns RetrievedDocument objects:
# [
#     RetrievedDocument(text="...", score=0.92),
#     RetrievedDocument(text="...", score=0.88),
#     ...
# ]
```

---

## Data Model Classes

### Pydantic Models (Request/Response)

```python
# File Upload Response
{
    "signal": "file_upload_success",
    "file_id": "abc123def456_strategy.txt"
}

# File Processing Request
{
    "file_id": "abc123def456_strategy.txt",  # Optional
    "chunk_size": 100,                        # Optional, default=100
    "overlap_size": 20,                       # Optional, default=20
    "do_reset": 0                             # Optional, default=0
}

# File Processing Response
{
    "signal": "file_process_success",
    "inserted_chunks": 250,
    "processed_files": 1
}

# NLP Index Push Request
{
    "do_reset": 0  # Optional, whether to reset collection
}

# NLP Index Push Response
{
    "signal": "insert_into_vectordb_success"
}

# NLP Collection Info Response
{
    "signal": "get_vectordb_collection_info_success",
    "collection_info": {
        "points_count": 250,
        "config": {...}
    }
}
```

### SQLAlchemy ORM Models

```python
# Project ORM
class Project(SQLAlchemyBase):
    project_id: int
    project_uuid: UUID
    created_at: datetime
    updated_at: datetime
    chunks: Relationship  # to DataChunk
    assets: Relationship  # to Asset

# DataChunk ORM
class DataChunk(SQLAlchemyBase):
    chunk_id: int
    chunk_uuid: UUID
    chunk_text: str
    chunk_metadata: dict  # JSONB
    chunk_order: int
    chunk_project_id: int  # FK
    chunk_asset_id: int    # FK
    created_at: datetime
    updated_at: datetime
    project: Relationship   # to Project
    asset: Relationship     # to Asset

# Asset ORM
class Asset(SQLAlchemyBase):
    asset_id: int
    asset_uuid: UUID
    asset_type: str  # "FILE"
    asset_name: str  # "abc123_file.txt"
    asset_size: int  # bytes
    asset_config: dict  # JSONB, optional
    asset_project_id: int  # FK
    created_at: datetime
    updated_at: datetime
    project: Relationship   # to Project
    chunks: Relationship    # to DataChunk
```

---

## Configuration & Environment

### Environment Variables
```env
# Application
APP_NAME=RAG Knowledge Engine
APP_DESCRIPTION=Retrieval-Augmented Generation system
APP_VERSION=1.0.0

# File Handling
FILE_ALLOWED_TYPES=["text/plain", "application/pdf"]
FILE_MAX_SIZE=10  # MB
FILE_DEFAULT_CHUNK_SIZE=512000  # ⚠️ Unclear units

# PostgreSQL (Async)
POSTGRES_USERNAME=postgres
POSTGRES_PASSWORD=your_postgres_password
POSTGRES_HOST=localhost  # ❌ Won't work in Docker
POSTGRES_PORT=5432
POSTGRES_DB=minirag-v1

# LLM - Generation
GENERATION_BACKEND=COHERE  # or OPENAI
GENERATION_MODEL_ID=command-a-03-2025
GENERATION_DAFAULT_MAX_TOKENS=200
GENERATION_DAFAULT_TEMPERATURE=0.1
OPENAI_API_KEY=...
OPENAI_API_URL=...

# LLM - Embedding
EMBEDDING_BACKEND=COHERE  # or OPENAI
EMBEDDING_MODEL_ID=embed-multilingual-light-v3.0
EMBEDDING_MODEL_SIZE=384
COHERE_API_KEY=...

# Text Processing
INPUT_DAFAULT_MAX_CHARACTERS=1024

# Vector Database
VECTOR_DB_BACKEND=QDRANT  # Only option currently
VECTOR_DB_PATH=qdrant_db  # ❌ Relative path
VECTOR_DB_DISTANCE_METHOD=cosine  # or dot
```

---

## Deployment Architecture

### Current Local Setup
```
Development Machine
├─ FastAPI Application (uvicorn)
│  ├─ Upload files → assets/files/{project_id}/
│  ├─ Store vectors → assets/database/qdrant_db/
│  └─ Connect to:
│     ├─ PostgreSQL (docker:5432)
│     └─ Qdrant (local storage)
│
├─ Docker Services
│  ├─ PostgreSQL (pgvector:0.8.2-pg18)
│  │  ├─ Port: 5432
│  │  └─ Volume: pgvector_data
│  │
│  └─ MongoDB (mongo:7) ❌ UNUSED
│     └─ Port: 27007
│
└─ File Storage
   └─ assets/
      ├─ files/{project_id}/*.txt  (uploaded files)
      └─ database/qdrant_db/       (vector store)
```

### Issues with Current Setup
1. Relative paths for file/database storage
2. `localhost` won't work if application in Docker
3. No persistent file storage mechanism
4. No backup/recovery
5. No load balancing
6. Single point of failure

---

## Performance Characteristics

### Data Processing Pipeline
```
File Upload:        O(file_size)     - Linear stream read
File Chunking:      O(file_size)     - Linear split
Vector Embedding:   O(chunks × model) - LLM API calls (slow)
Vector Indexing:    O(chunks × dim)   - Qdrant insert
Vector Search:      O(log n)          - Approximate NN search
Answer Generation:  O(context_size)   - LLM API call (slow)
```

### Bottlenecks
1. **LLM API Calls** - Embedding and generation are network I/O bound
2. **Vector Search** - Linear scan if no indexing (with indexing_threshold=0)
3. **File Processing** - TextLoader reads entire file into memory
4. **Database Inserts** - Batch size of 100 might be too small

### Optimization Opportunities
1. Batch embeddings API calls
2. Use Qdrant indices instead of linear scan
3. Stream file processing instead of loading all to memory
4. Cache embeddings
5. Add database connection pooling
6. Implement vector quantization for smaller embeddings

