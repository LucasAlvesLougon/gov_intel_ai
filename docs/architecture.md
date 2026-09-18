# Arquitetura do GovIntel AI

```mermaid
flowchart TD
  UI[Next.js 15] --> API[Django REST Framework]
  API --> DB[(PostgreSQL 16 + pgvector)]
  API --> REDIS[(Redis)]
  API --> MQ[RabbitMQ]
  MQ --> CEL[Celery Worker]
  CEL --> PDF[Extração e chunking]
  PDF --> EMB[Local multilingual-e5-base / 768D]
  EMB --> DB
  API --> RET[Retrieval vetorial]
  RET --> LLM[OpenCode Zen]
```

O limite de segurança principal é `company_id` derivado do usuário autenticado. Toda consulta de edital, chunk, conversa e cache deve incluir esse limite.

O upload cria uma tarefa Celery e retorna antes do processamento. O worker preserva página e trecho de cada chunk para que o chat consiga devolver citações verificáveis.

LLM e embeddings são configurações independentes. O embedding local usa os
prefixos `passage:` e `query:`, batch CPU, normalização L2 e fingerprint
persistido no chunk. O retrieval exige a identidade completa do fingerprint,
não somente o provider. A reindexação grava uma geração staged para todo o
conjunto selecionado e promove em transação; a geração anterior é preservada
para rollback.
