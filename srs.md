# Software Requirements Specification (SRS)

## 1. Introduction

### 1.1 Purpose
This document defines the software requirements for the `RAG Knowledge Engine` project. The system is a backend service for document upload, processing, translation, indexing, semantic search, and retrieval-augmented answer generation.

### 1.2 Scope
The project provides a FastAPI-based API that allows clients to:

- create and manage project knowledge bases
- upload files into a project
- process uploaded files into chunks
- generate embeddings for chunks
- store vectors in a vector database
- search indexed content semantically
- generate answers using retrieved context
- translate files through a translation provider

### 1.3 Intended Audience
This document is intended for:

- backend developers
- QA engineers
- system integrators
- project stakeholders

## 2. Product Overview

### 2.1 Product Perspective
The system is a modular backend organized into:

- `routes` for API endpoints
- `controllers` for business logic
- `models` for domain and database access
- `stores` for LLM, translation, and vector database providers
- `helpers` for configuration and file handling utilities

### 2.2 Product Goals
The system should:

- accept user files and associate them with a project
- transform raw files into searchable chunks
- support vector indexing for RAG workflows
- return relevant search results from indexed data
- support AI answer generation from retrieved context
- support file translation workflows

## 3. System Features

### 3.1 Project Management
The system shall create a project record automatically when a valid project identifier is used in upload, processing, indexing, or search operations.

### 3.2 File Upload
The system shall:

- accept file upload requests under a project identifier
- validate file type and file size
- generate a unique stored file name
- save the file on disk
- create an asset record in the database

### 3.3 File Processing
The system shall:

- retrieve project files from storage
- parse supported file types
- split extracted content into chunks
- store generated chunks in the relational database
- support reset behavior for reprocessing

### 3.4 Vector Indexing
The system shall:

- create a vector collection for each project
- generate embeddings for stored chunks
- insert vectors into the configured vector database
- create a vector index after insertion

### 3.5 Semantic Search
The system shall:

- accept text queries for a project
- embed the query text
- search the project vector collection
- return ranked results with scores and metadata

### 3.6 RAG Answer Generation
The system shall:

- retrieve relevant context from the vector database
- build a prompt from the retrieved context and the user query
- generate an answer through the configured LLM provider
- return the answer and supporting prompt context

### 3.7 Translation
The system shall:

- support translation of uploaded files through a translation provider
- validate translation parameters
- handle provider failures and retries
- save translated output as a project asset when applicable

## 4. Functional Requirements

### 4.1 API Requirements
The backend shall expose HTTP endpoints for:

- base health or root operations
- file upload and file processing
- vector indexing and collection info
- semantic search and answer generation
- translation workflows

### 4.2 Upload Requirements

- The system shall reject unsupported file types.
- The system shall reject files that exceed the configured maximum size.
- The system shall store uploaded files under a project-specific path.
- The system shall return a success signal and stored file identifier after upload.

### 4.3 Processing Requirements

- The system shall support chunk size and overlap configuration.
- The system shall process either a specific file or all files in a project.
- The system shall store each chunk with text, metadata, order, project reference, and asset reference.

### 4.4 Indexing Requirements

- The system shall page through stored chunks during indexing.
- The system shall support resetting the vector collection before re-indexing.
- The system shall create a vector index after all chunks are inserted.

### 4.5 Search Requirements

- The system shall return ranked search results for a project.
- Each result shall include chunk text, similarity score, and metadata.

### 4.6 Answering Requirements

- The system shall generate answers only from indexed project data.
- The system shall return an error signal when no answer can be produced.

### 4.7 Translation Requirements

- The system shall validate source and target languages.
- The system shall retry transient translation provider failures.
- The system shall report translation errors in a structured way.

## 5. External Interface Requirements

### 5.1 API Interface
The primary interface shall be a REST API over HTTP using FastAPI.

### 5.2 Database Interface
The system shall use:

- PostgreSQL for structured project, asset, chunk, and translation job data
- Qdrant or pgvector-compatible vector storage for embeddings

### 5.3 AI Provider Interface
The system shall integrate with:

- OpenAI for generation and embeddings
- Cohere for generation and embeddings

### 5.4 Translation Interface
The system shall integrate with a translation provider compatible with the current translation store abstraction, including LibreTranslate-based flows.

## 6. Data Requirements

### 6.1 Core Entities
The system shall manage at minimum the following entities:

- Project
- Asset
- DataChunk
- TranslationJob

### 6.2 Stored Data
The system shall store:

- uploaded file metadata
- processed chunk text
- chunk metadata
- vector embeddings in the vector database
- translation job metadata and outputs

## 7. Non-Functional Requirements

### 7.1 Performance

- The system should handle chunked file processing efficiently for medium-sized documents.
- The system should batch vector insert operations where supported.
- The system should avoid blocking operations in request handling where asynchronous alternatives exist.

### 7.2 Reliability

- The system shall return structured error responses for invalid requests and provider failures.
- The system shall dispose of database and vector connections during shutdown.
- The system should retry transient translation provider failures.

### 7.3 Maintainability

- The codebase should preserve separation between routes, controllers, models, and provider stores.
- Configuration should remain centralized through environment-based settings.
- Provider implementations should remain replaceable through factory abstractions.

### 7.4 Scalability

- The system should support adding additional LLM providers.
- The system should support more than one vector backend through the vector provider factory.
- The system should support growth in project count and chunk volume by project isolation.

### 7.5 Security

- The system should validate uploaded file inputs before storage.
- Sensitive provider credentials shall be supplied through environment variables.
- The system should restrict unsafe file handling and unsupported input types.

## 8. Assumptions and Constraints

### 8.1 Assumptions

- The client provides valid project identifiers.
- Required external services and API keys are available in the runtime environment.
- The selected embedding model dimension matches the vector collection configuration.

### 8.2 Constraints

- The project currently depends on external LLM and translation providers for core AI features.
- Runtime behavior depends on environment configuration values.
- File parsing behavior is limited by currently supported file handlers.

## 9. Current In-Scope Endpoints

- `POST /api/v1/data/upload/{project_id}`
- `POST /api/v1/data/process/{project_id}`
- `POST /api/v1/nlp/index/push/{project_id}`
- `GET /api/v1/nlp/index/info/{project_id}`
- `POST /api/v1/nlp/index/search/{project_id}`
- `POST /api/v1/nlp/index/answer/{project_id}`
- translation endpoints under the translation router

## 10. Future Enhancements

- authentication and authorization
- richer monitoring and logging
- improved file parser coverage
- batching and caching for embeddings
- deployment-ready storage and backup strategy
