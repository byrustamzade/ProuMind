# ProuMind

> Enterprise AI Knowledge Platform powered by RAG, GraphRAG, Hybrid Retrieval, Elasticsearch, Neo4j, and LLMs.

ProuMind is a production-oriented AI knowledge platform designed to ingest information from multiple sources, build a searchable knowledge base, create a knowledge graph, and provide grounded answers using Retrieval-Augmented Generation (RAG) and GraphRAG techniques.

The project demonstrates real-world AI engineering concepts including:

- RAG
- GraphRAG
- Hybrid Search
- Retrieval Engineering
- Knowledge Graphs
- Background Processing
- Vector Search
- Elasticsearch
- Neo4j
- LLM Orchestration
- Async Workers
- Enterprise AI Architecture

---

## Features

### Knowledge Ingestion

#### PDF Upload

- PDF document upload
- Duplicate detection
- SHA256 content hashing
- Metadata storage
- Background processing

#### OCR Fallback

Supports scanned PDFs and image-based documents.

#### Website Ingestion

- Website URL ingestion
- HTML parsing
- Readable text extraction
- Background processing

---

### Retrieval

#### Hybrid Search

Combines:

- BM25 keyword search
- Vector similarity search

using Elasticsearch.

#### Reranking

Cross-encoder reranking improves retrieval quality by reordering candidate chunks based on relevance to the user question.

#### Metadata Filtering

Filter retrieval by:

- document
- source type
- future workspace/project filters

---

### GraphRAG

#### Knowledge Graph

Automatically extracts:

- entities
- relationships

and stores them in Neo4j.

#### Multi-Hop Graph Traversal

Supports traversing relationships across multiple nodes to discover indirect connections.

#### Graph-Expanded Retrieval

Knowledge graph entities are used to expand retrieval queries and improve answer quality.

---

### AI Answering

#### Supported Providers

- Ollama (default)
- OpenAI (optional)

#### Grounded Responses

Answers are generated only from retrieved context.

#### Explainability

Debug mode shows:

- retrieved chunks
- scores
- graph context
- expansion terms

---

### Background Processing

#### Redis Queue

Document ingestion runs asynchronously.

#### RQ Workers

Heavy operations are moved out of API requests:

- OCR
- chunking
- embeddings
- indexing
- graph extraction

---

### Job Management

#### Ingestion Jobs

Track processing state:

```text
pending
processing
completed
failed
```

#### Retry Failed Jobs

Failed ingestion jobs can be retried.

#### Reprocess Documents

Documents can be reprocessed without reuploading.

---

## Architecture

```text
                  ┌────────────────────┐
                  │     Data Sources   │
                  └──────────┬─────────┘
                             │
             ┌───────────────┼───────────────┐
             │                               │
             ▼                               ▼
         PDF Upload                    Website URL
             │                               │
             └───────────────┬───────────────┘
                             │
                             ▼
                       FastAPI API
                             │
                             ▼
                    PostgreSQL Storage
                             │
                             ▼
                     Redis Job Queue
                             │
                             ▼
                      RQ Background Worker
                             │
       ┌─────────────────────┼─────────────────────┐
       │                     │                     │
       ▼                     ▼                     ▼
    OCR/Text             Chunking            Embeddings
   Extraction           (LlamaIndex)
       │                     │                     │
       └─────────────────────┼─────────────────────┘
                             │
              ┌──────────────┴──────────────┐
              │                             │
              ▼                             ▼
        Elasticsearch                  Neo4j Graph
         Hybrid Search             Entity Relationships
              │                             │
              └──────────────┬──────────────┘
                             │
                             ▼
                      GraphRAG Retrieval
                             │
                             ▼
                        LLM Provider
                    (Ollama/OpenAI)
                             │
                             ▼
                         Final Answer
```

---

## Technology Stack

### Backend

- FastAPI
- SQLAlchemy
- Alembic
- PostgreSQL

### Search

- Elasticsearch
- BM25
- Vector Search

### AI

- Ollama
- OpenAI
- Sentence Transformers
- Cross Encoder Reranking

### Knowledge Graph

- Neo4j

### Processing

- Redis
- RQ Workers

### Parsing

- LlamaIndex
- BeautifulSoup
- OCR

### Infrastructure

- Docker
- Docker Compose

---

## API Endpoints

### Documents

#### Upload PDF

```http
POST /documents/upload
```

#### Ingest Website

```http
POST /documents/url
```

#### List Documents

```http
GET /documents
```

#### Search Documents

```http
GET /documents/search
```

---

### AI

#### Ask Questions

```http
POST /ask
```

Example:

```json
{
  "question": "Which languages does Mahammad speak?",
  "size": 10,
  "debug": true
}
```

---

### Ingestion Jobs

#### List Jobs

```http
GET /documents/ingestion-jobs
```

#### Job Details

```http
GET /documents/ingestion-jobs/{job_id}
```

#### Retry Failed Job

```http
POST /documents/ingestion-jobs/{job_id}/retry
```

#### Reprocess Document

```http
POST /documents/{document_id}/reprocess
```

---

## Current Capabilities

✅ PDF ingestion

✅ OCR support

✅ Website ingestion

✅ Async background processing

✅ Elasticsearch indexing

✅ Hybrid retrieval

✅ Cross-encoder reranking

✅ Neo4j knowledge graph

✅ Multi-hop graph traversal

✅ Graph-expanded retrieval

✅ Ollama integration

✅ OpenAI integration

✅ Explainable retrieval

✅ Job tracking

---

## Roadmap

### Connectors

- GitHub Issues
- GitHub Pull Requests
- Jira
- Slack
- Confluence

### Orchestration

- n8n workflows
- Scheduled ingestion
- Webhook ingestion

### Enterprise Features

- Multi-tenant architecture
- Workspaces
- Role-based access control
- Evaluation framework
- Monitoring

### Visualization

- Graph explorer
- Knowledge graph UI
- Dashboard

### Advanced AI

- AI Agents
- Tool Calling
- Autonomous Research Workflows

---

## Project Goal

ProuMind was built to demonstrate practical AI engineering skills beyond simple chatbots.

The focus is on building production-style systems that combine:

- Retrieval-Augmented Generation (RAG)
- GraphRAG
- Knowledge Graphs
- Search Infrastructure
- Async Processing
- Enterprise Architecture
- LLM Orchestration

into a unified AI knowledge platform.