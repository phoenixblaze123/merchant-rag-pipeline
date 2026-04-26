# Merchant RAG Pipeline 🏦

**Production-grade Retrieval-Augmented Generation (RAG) pipeline for
Merchant Revenue Intelligence** — built on Databricks, AWS Bedrock,
Delta Lake, and LangChain.

## Architecture
S3 (Raw Docs)
│
▼
[Bronze] Raw ingestion → Delta table
│
▼
[Silver] Chunking + PII masking + metadata enrichment
│
▼
[Gold]  Embeddings → Databricks Vector Search Index
│
▼
[RAG Chain] Hybrid Search + AWS Bedrock (Claude 3.5 Sonnet)
│
▼
[Evaluation] RAGAS metrics + MLflow tracking

## Key Features

- ✅ Medallion Architecture (Bronze → Silver → Gold)
- ✅ Hybrid Search (vector + BM25) via Databricks Vector Search
- ✅ PII Masking with Presidio before indexing
- ✅ RAGAS evaluation with MLflow tracking
- ✅ Unity Catalog governance + RBAC
- ✅ AWS Bedrock (Claude 3.5 Sonnet + Titan Embeddings)

## Stack

| Layer | Technology |
|---|---|
| Orchestration | Databricks Workflows |
| Storage | S3 + Delta Lake |
| Vector Store | Databricks Vector Search |
| Embedding | Amazon Titan Embed v2 |
| LLM | Claude 3.5 Sonnet (Bedrock) |
| Chain Framework | LangChain LCEL |
| Governance | Unity Catalog |
| Monitoring | MLflow + RAGAS |
| IaC | Terraform |

## Quick Start

```bash
git clone https://github.com/YOUR-USERNAME/merchant-rag-pipeline.git
cd merchant-rag-pipeline
cp .env.example .env        # fill in your credentials
pip install -r requirements.txt
```

## Notebooks

| # | Notebook | Description |
|---|---|---|
| 01 | Bronze Ingestion | Load raw merchant docs from S3 into Delta |
| 02 | Silver Chunking | Chunk + PII mask + metadata enrichment |
| 03 | Gold Embedding | Embed + sync to Databricks Vector Search |
| 04 | RAG Chain | LangChain LCEL hybrid search + generation |
| 05 | Evaluation | RAGAS metrics + MLflow experiment logging |

## Author

Senior Data Engineer / GenAI Architect | Databricks + AWS
