# Capability Map: GovIntel AI

O GovIntel AI contém capacidades independentes que podem ser implementadas e verificadas separadamente. Os ids abaixo são estáveis e devem ser usados em specs e tarefas.

| Módulo | Responsabilidade | Depende de |
|---|---|---|
| `local-infrastructure` | Docker Compose, PostgreSQL/pgvector, Redis e RabbitMQ locais | — |
| `identity-tenant` | Empresas, usuários, JWT e isolamento multi-tenant | `local-infrastructure` |
| `tender-management` | Metadados, upload e ciclo de vida dos editais | `identity-tenant` |
| `document-pipeline` | RabbitMQ, Celery, extração, chunking e estados | `identity-tenant`, `tender-management` |
| `vector-intelligence` | Embeddings, pgvector, busca semântica e retrieval | `document-pipeline` |
| `rag-chat` | Conversas, respostas fundamentadas e citações | `vector-intelligence` |
| `cache-protection` | Redis, cache e rate limiting | `identity-tenant`, `vector-intelligence`, `rag-chat` |
| `web-application` | Interface Next.js para o fluxo completo | APIs dos módulos anteriores |
| `delivery-operations` | CI/CD e deploy da demonstração | Todos os módulos |

## Ordem de construção

`local-infrastructure` → `identity-tenant` → `tender-management` → `document-pipeline` → `vector-intelligence` → `rag-chat` → `cache-protection` → `web-application` → `delivery-operations`

Cada módulo deve passar por Specify, Plan, Tasks e aprovação antes de avançar para implementação.
