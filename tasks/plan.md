# Implementation Plan: GovIntel AI

## Overview

Implementar a demo de inteligência sobre editais em fatias verticais. Cada checkpoint deixa um fluxo executável e verificável, seguindo o [CAPABILITY-MAP.md](../CAPABILITY-MAP.md) e os contratos de [docs/api-contract.md](../docs/api-contract.md).

## Architecture Decisions

- `local-infrastructure` é pré-requisito operacional.
- O backend é a autoridade de autenticação, tenant e regras de negócio.
- Tasks Celery usam entrega at-least-once e são idempotentes por `jobId`.
- Upload exige `Idempotency-Key` para retries seguros.
- O padrão atual separa LLM e embeddings: OpenCode Zen para chat e
  `intfloat/multilingual-e5-base` local em CPU, com 768 dimensões, prefixos E5,
  batch, cache e fingerprint. Providers legados permanecem explícitos.
- PostgreSQL/pgvector é fonte de verdade; Redis é cache e throttling.
- Frontend com mocks só depois do contrato da fatia ser aprovado.
- Outbox, lease/heartbeat e compare-and-set são necessários para tratar a entrega at-least-once como contrato real.
- Citações só são emitidas após validação contra IDs e quotes do retrieval; o LLM não cria fontes.
- PDFs usam `storage_key` em volume privado no MVP; remoção cobre blob, chunks, cache e conversas.
- Chunks são versionados por `pipeline_generation`; somente a geração current é pesquisável.

## Dependency Graph

```text
Compose → Django config → Company/User/JWT → Tender → Upload
  → Celery/Extraction → Chunking → Embeddings/pgvector
  → Retrieval → RAG/Citations → Redis → Frontend → CI/CD
```

## Task List

### Phase 1: Local infrastructure and identity

- [x] Tasks 1–7: Compose, scaffolding, empresa, usuário, JWT e isolamento

### Checkpoint: Foundation

- [x] Compose inicia `db`, `redis`, `rabbitmq`, `api`, `worker` e `frontend` com health checks.
- [x] Registro, login, refresh e `/me/` funcionam.
- [x] Teste comprova isolamento entre dois tenants.
- [x] Security preflight confirma cookies, CORS, headers, secrets e logs.

### Phase 2: Tender ingestion and asynchronous processing

- [x] Tasks 8–13: edital, upload, idempotência, extração e estados

### Checkpoint: Ingestion

- [x] Upload retorna `202` sem bloquear o processamento.
- [x] Status percorre `PENDING → PROCESSING → PROCESSED` ou `FAILED`.
- [x] Fixture PDF produz chunks com página e offsets.

### Phase 3: Vector intelligence and RAG

- [x] Tasks 14–19: embeddings, pgvector, busca e chat

### Checkpoint: Intelligence

- [x] Busca retorna resultados filtrados por tenant com score e página.
- [x] Chat responde somente com contexto recuperado.
- [x] Cada resposta factual contém citação verificável.

### Phase 4: Cache and protection

- [x] Tasks 20–22: Redis, invalidação e throttling

### Checkpoint: Protection

- [x] Segunda busca equivalente produz cache hit.
- [x] Cache nunca cruza tenants.
- [x] Limites retornam `429` de forma consistente.

### Phase 5: Web application

- [x] Tasks 23–28: cliente, telas, estados e E2E

### Checkpoint: Demo

- [x] Cadastro → upload → processamento → busca → chat funciona no navegador.
- [x] Loading, vazio, erro e citações são visíveis.
- [x] Playwright passa em ambiente limpo.

### Phase 6: Delivery

- [x] Tasks 29–32: CI, auditoria de dependências, documentação e preparação de deploy

### Checkpoint: Complete

- [ ] Lint, testes e build passam no CI.
- [x] README permite reproduzir a demo do zero.
- [x] Roteiro de demonstração está atualizado.
- [x] Security acceptance gate em `docs/security-threat-model.md` está concluído.

## Parallelization

Podem ocorrer em paralelo após contratos aprovados: componentes frontend com mocks, testes de contrato, README e documentação. Devem ser sequenciais: migrations compartilhadas, processamento de documentos, definição da dimensão vetorial e retrieval. CI só deve fixar comandos depois que os serviços existirem.

## Risks and Mitigations

| Risco | Impacto | Mitigação |
|---|---|---|
| Dimensão de embeddings muda | Alto | Fixar 768, validar startup e re-embeddings explícitos |
| PDF sem camada de texto | Alto | Detectar texto vazio e terminar em `FAILED` |
| Redelivery duplica chunks | Alto | `jobId`, constraints e task idempotente |
| Query sem filtro de tenant | Alto | Querysets centralizados e teste cross-tenant |
| UI diverge da API | Médio | Contrato central e mocks tipados |
| Quota de IA excedida | Médio | Cache, throttling, retry limitado e fixtures |
| Outbox/lease ausentes | Alto | Teste de broker indisponível, reconciliador e timeout de processamento |
| Citação fabricada | Alto | Schema estruturado, allowlist de chunk IDs e quote exata |
| Refresh CSRF/replay | Alto | CSRF/origin check, rotação e revogação |
| Storage/retention incorretos | Alto | Adapter privado, cleanup transacional e retenção configurável |

## Open Questions

- Render foi escolhido como alvo de preparação; publicação depende de storage compartilhado e autorização explícita.
- O email continuará único globalmente se o produto futuramente permitir o mesmo usuário em várias empresas?

## Pós-demo — qualidade de busca e chat (2026-09-17)

Implementação concluída após reprodução manual: reranking lexical híbrido para
o modo mock, snippets centrados nos termos, resposta RAG concisa com grounding,
campo `quote` nas citações e adapter Embedding 2 conforme a SPEC. Evidência:
118 testes backend, 34 testes frontend, Ruff, Django check, Compose config e
E2E Playwright 1/1.

## Correção pós-demo — CSRF entre hosts locais (2026-09-17)

O cliente agora remapeia `localhost`/`127.0.0.1` da API para o hostname usado
na página, evitando que `SameSite=Lax` descarte o cookie CSRF. A regressão foi
validada no cadastro e login de ambos os hosts; 43 testes frontend, lint,
typecheck, build e quatro execuções E2E de CSRF passaram.

## Pós-demo — estabilização de sessão, CI e chat real (2026-09-17)

Implementado e verificado: CSRF e refresh com reuse detection, throttling
fail-closed, traversal de storage, erros sanitizados, Pillow 12.3.0, serviços
de CI com health checks, metadados/isolation de provider e comando de
reindexação. Vinte e nove editais foram reindexados no OpenRouter (55 chunks
atuais); as citações agora são fail-closed com uma tentativa corretiva. Gates:
151 pytest backend, 42 Vitest, lint/typecheck frontend, Ruff, Django check,
migrations check, `docker compose config --quiet`, `pip-audit --strict`, worker
ping e chat real com 6 citações verificadas.

## Redesign frontend — 2026-09-17

Implementada a direção visual “Centro de Inteligência de Licitações” com
tokens editoriais, tipografia serif/sans, rail de evidências, estados acessíveis
e responsividade. A implementação refez a fundação em
`frontend/app/globals.css` e aplicou classes de shell à home/autenticação;
dashboard, busca e chat passaram a compartilhar a mesma linguagem sem alteração
de API, autenticação ou IDs de automação. `docs/frontend/` registra as decisões
e os cinco guias de revisão. Evidência: rebuild Next concluído, 43 Vitest,
lint/Prettier, typecheck e build passando; rotas públicas e telas vazias
conferidas no navegador real em 1280x720.
Capturas reproduzíveis foram salvas em `docs/frontend/evidence/`; smoke test
Playwright não encontrou page errors e registrou apenas 401 esperado nas
chamadas protegidas sem sessão.
