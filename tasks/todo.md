# Task List: GovIntel AI

Cada tarefa cabe em uma sessão focada, toca no máximo cinco arquivos principais e deixa o sistema compilável/testável. Não iniciar uma tarefa enquanto suas dependências não estiverem concluídas.

## Phase 1 — Local infrastructure and identity

Nota de execução (2026-09-16): Task 1 valida configuração e serviços de dados
antes dos scaffolds; o teste dos seis serviços permanece obrigatório no
checkpoint Tasks 1–3. Tasks 2–3 podem completar essa dependência técnica dentro
de local-infrastructure. Ver [decisão](../docs/implementation-decisions.md).

### Task 1: Criar serviços locais do Compose
**Description:** Definir `db`, `redis`, `rabbitmq`, `api`, `worker` e `frontend`, redes, volumes, variáveis e health checks.
**Acceptance criteria:**
- [x] `docker compose up -d` inicia os serviços.
- [x] `api` e `worker` dependem de serviços saudáveis.
- [x] Segredos ficam apenas em `.env`.
- [x] `.gitignore` exclui `.env`, `.env.local`, `*.key` e `*.pem`.
**Verification:** `docker compose config` e `docker compose ps`.
**Dependencies:** None
**Files likely touched:** `docker-compose.yml`, `.env.example`
**Estimated scope:** Medium

Evidência 2026-09-16: `docker compose config --quiet` passou; db/redis/rabbitmq
saudáveis; PostgreSQL 16.15 com extensão vector 0.8.6 disponível; Redis PONG e
RabbitMQ ping passaram. API/worker saudáveis após Task 2; frontend pendente.

### Task 2: Criar scaffolding Django e configurações
**Description:** Criar projeto Django, apps base, settings, URLs, PostgreSQL, Celery e endpoint `/health/`.
**Acceptance criteria:**
- [x] `manage.py check` passa.
- [x] API conecta ao PostgreSQL.
- [x] Worker importa a aplicação Celery.
- [x] `GET /health/` retorna `200` sem expor segredos.
**Verification:** `docker compose exec api python manage.py check` e logs do worker.
**Dependencies:** Task 1
**Files likely touched:** `backend/manage.py`, `backend/config/settings.py`, `backend/config/celery.py`, `backend/config/urls.py`
**Estimated scope:** Medium

Evidência 2026-09-16: 5 testes pytest passaram com PostgreSQL real; Ruff passou;
`manage.py check` sem problemas; GET localhost:8000/health/ retornou 200;
Celery inspect ping retornou pong. Fila govintel.pipeline e DLQ govintel.dead
duráveis, declaradas antes do worker. Relay/outbox permanece na Task 13.

### Task 3: Criar scaffolding Next.js
**Description:** Criar Next.js 15, TypeScript, ESLint, Prettier e cliente HTTP.
**Acceptance criteria:**
- [x] `next dev` inicia.
- [x] `next build` passa sem API.
- [x] Base URL vem do ambiente.
**Verification:** `docker compose exec frontend npm run build`.
**Dependencies:** Task 1
**Files likely touched:** `frontend/package.json`, `frontend/tsconfig.json`, `frontend/app/page.tsx`, `frontend/lib/http.ts`
**Estimated scope:** Medium

Evidência 2026-09-16: build Next.js 15.5.25 no Docker sem API durante build;
smoke isolado de `next dev` retornou 200; 3 testes Vitest, lint/Prettier e
typecheck passaram; npm audit sem vulnerabilidades. Página verificada no
navegador em desktop/320px, sem avisos/erros de console. Seis serviços saudáveis
após recriação sem apagar volumes e portas 127.0.0.1 verificadas.

## Checkpoint: Infrastructure scaffold
- [x] Tasks 1–3 concluídas.
- [x] Compose, health endpoint e build inicial funcionam.
- [x] Contratos foram revisados antes do schema de domínio.

### Task 4: Criar modelos Company e User
**Description:** Implementar usuário customizado, empresa, UUIDs, role `OWNER`, slug e constraints.
**Acceptance criteria:**
- [x] Migration cria tabelas e constraints.
- [x] Email é único globalmente.
- [x] `company_id` é obrigatório.
**Verification:** `python manage.py makemigrations --check` e testes de integridade.
**Dependencies:** Task 2
**Files likely touched:** `backend/apps/core/models.py`, `backend/apps/core/admin.py`, migration
**Estimated scope:** Medium

Evidência 2026-09-16: migration 0001_initial aplicada no PostgreSQL real; Company e User
criados com UUIDs, slug autogerado com sufixo randômico único, Lower constraint de email,
company FK com PROTECT, role OWNER via CheckConstraint; 10/10 pytest passaram;
makemigrations --check limpo; ruff check . sem erros; django check sem pendências.

### Task 5: Implementar registro transacional
**Description:** Criar serializer, serviço e endpoint de registro atômico.
**Acceptance criteria:**
- [x] Registro válido retorna `201`.
- [x] Email duplicado retorna `409`.
- [x] Falha não deixa empresa parcial.
**Verification:** `pytest backend/tests/integration/test_identity_tenant.py -k register`.
**Dependencies:** Task 4
**Files likely touched:** `backend/apps/core/serializers.py`, `services.py`, `views.py`, teste
**Estimated scope:** Medium

Evidência 2026-09-16: POST /api/auth/register/ implementado e testado; transação atômica
garante que falha na criação do usuário faz rollback total da empresa; duplicação de email
retorna 409 CONFLICT com mensagem genérica no envelope comum; refresh_token emitido em
cookie httpOnly protegido e access token em memória; 4 testes de integração passaram em
pytest backend/tests/integration/test_identity_tenant.py -k register; ruff check . sem erros.

### Task 6: Implementar JWT, refresh e `/me/`
**Description:** Configurar SimpleJWT e endpoints de token e identidade autenticada.
**Acceptance criteria:**
- [x] Login, refresh e `/me/` seguem o contrato.
- [x] Token inválido e usuário inativo retornam `401`.
- [x] Credencial inválida não revela existência do email.
- [x] Access token fica somente em memória e refresh usa cookie `httpOnly`, `secure` fora de localhost e `sameSite` configurado.
- [x] Access expira em 15 minutos; refresh em 7 dias, com rotação, blacklist, logout, reuse detection e CSRF/origin check.
- [x] Handler global de exceções converte auth, parser, throttling e falhas não tratadas ao envelope comum.
**Verification:** `pytest backend/tests/integration/test_identity_tenant.py -k 'login or refresh or me'`.
**Dependencies:** Task 5
**Files likely touched:** `backend/config/settings.py`, `backend/apps/core/urls.py`, `views.py`, teste
**Estimated scope:** Medium

Evidência 2026-09-16: SimpleJWT configurado (access 15m, refresh 7d com rotação e blacklist);
login com CaseInsensitiveModelBackend e proteção de timing; refresh por cookie protegido com
detecção de reúso; logout com revogação e remoção de cookie; /me autenticado por Bearer token;
envelope comum de erro padronizado; 13 testes de integração cobrindo o fluxo completo passaram
em pytest backend/tests/integration/test_identity_tenant.py; ruff check . limpo.

## Checkpoint: Authentication contract
- [x] Tasks 4–6 concluídas.
- [x] Migration, registro, login, refresh e `/me/` passam.
- [x] Cookies e exposição de tokens seguem a threat model.

### Task 7: Criar permissão e teste cross-tenant
**Description:** Centralizar helpers que derivam a empresa de `request.user`.
**Acceptance criteria:**
- [x] Nenhuma permissão aceita `companyId` do payload.
- [x] Recurso de outro tenant é invisível ou negado conforme contrato.
- [x] Existe teste com duas empresas.
**Verification:** `pytest backend/tests/integration/test_identity_tenant.py -k tenant`.
**Dependencies:** Task 6
**Files likely touched:** `backend/apps/core/permissions.py`, `services.py`, teste
**Estimated scope:** Small

Evidência 2026-09-16: backend/apps/core/permissions.py implementado com get_user_company,
filter_by_tenant e IsTenantMember; derivação estrita da empresa a partir do usuário autenticado;
teste com duas empresas (Empresa A e Empresa B) confirma isolamento mútuo em /me/ e em nível de ORM;
rejeição de payloads adulterados com companyId arbitrário; 25 testes pytest passando no backend;
3 testes Vitest passando no frontend; ruff check . e manage.py check limpos.

## Checkpoint: Foundation
- [x] Tasks 1–7 concluídas.
- [x] `docker compose ps` saudável.
- [x] Testes de autenticação e isolamento passam.
- [x] Revisar com humano antes da Fase 2.

## Phase 2 — Tender ingestion and pipeline

### Task 8: Criar modelo e listagem de Tender
**Description:** Implementar metadados, estados, queryset paginado e serializers.
**Acceptance criteria:**
- [x] CRUD lista apenas o tenant.
- [x] Estados são os quatro valores documentados.
- [x] Paginação e filtros funcionam.
**Verification:** testes de model, serializer e `GET /api/tenders/`.
**Dependencies:** Task 7
**Files likely touched:** `backend/apps/tenders/models.py`, serializers, views, migration, teste
**Estimated scope:** Medium

Evidência 2026-09-16: Tender model implementado com UUID, status PENDING/PROCESSING/PROCESSED/FAILED
com CheckConstraint, company FK com CASCADE; TenderPublicSerializer em camelCase; listagem
paginada ({data, pagination}, page, pageSize max 50, ordenação e filtro por status); detail view
com 404 para outros tenants; migration 0001_initial de tenders aplicada; 6 testes de integração
passaram em pytest backend/tests/integration/test_tender_management.py; ruff check . limpo.

### Task 9: Implementar upload e validação de PDF
**Description:** Aceitar multipart, validar e salvar PDF em `PENDING`.
**Acceptance criteria:**
- [x] PDF válido retorna `202`.
- [x] Arquivo inválido retorna erro estruturado.
- [x] Arquivo pertence ao tenant autenticado.
- [x] MIME, magic bytes, tamanho máximo e arquivo vazio são rejeitados no backend.
- [x] Nome original não é usado como caminho público.
- [x] PDF é gravado por `storage_key` em volume privado, com adapter e política de retenção.
- [x] Exclusão agenda cleanup de blob/chunks/cache/conversas e uma varredura detecta órfãos.
**Verification:** testes multipart válido, corrompido e não-PDF.
**Dependencies:** Task 8
**Files likely touched:** serializers, views, validators, teste
**Estimated scope:** Medium

Evidência 2026-09-16: upload multipart implementado em POST /api/tenders/ retornando 202 com status
PENDING; validação rigorosa de PDF (rejeição de arquivo vazio 400, limite 50MB e magic bytes b'%PDF-');
armazenamento privado por chave segura {company_id}/{tender_id}.pdf em LocalStorageAdapter; sha256 e
tamanho persistidos; exclusão DELETE /api/tenders/{id}/ com remoção autorizada do blob e rejeição
cross-tenant 404; 11 testes de integração em test_tender_management.py passaram; ruff check . limpo.

### Task 10: Implementar idempotência do upload
**Description:** Persistir `Idempotency-Key` e hash canônico do request com constraint única por tenant, usuário e endpoint.
**Acceptance criteria:**
- [x] Retry igual reproduz o mesmo edital.
- [x] Chave com payload diferente retorna `422`.
- [x] Duplicata em andamento retorna `202`.
- [x] Hash usa bytes do PDF em streaming e metadados canonizados, sem depender do boundary multipart.
- [x] Chave é escopada por tenant, usuário e endpoint, com hash do body e cleanup documentado.
**Verification:** teste duplicado e concorrente.
**Dependencies:** Task 9
**Files likely touched:** `models.py`, migration, service, teste
**Estimated scope:** Medium

Evidência 2026-09-16: IdempotencyKey model implementado com UniqueConstraint(company, user, endpoint, key);
cálculo canônico do hash do request com sha256 do arquivo e metadados (independente de boundary);
select_for_update atômico; retry idêntico reproduz o mesmo edital retornando 202; chave com payload modificado
retorna 422 UNPROCESSABLE_ENTITY; chave escopada por tenant e usuário; migration 0002_idempotencykey aplicada;
39 testes pytest passando no total (14 em test_tender_management.py); ruff check . limpo; django check limpo.

## Checkpoint: Upload contract
- [x] Tasks 8–10 concluídas.
- [x] CRUD, validação de PDF e idempotência passam.
- [x] Contrato revisado antes de conectar o worker.

### Task 11: Criar endpoint de status
**Description:** Expor status, progresso, chunks processados e erro seguro.
**Acceptance criteria:**
- [x] Status é tenant-aware.
- [x] Resposta segue o contrato.
- [x] Stack trace não aparece.
**Verification:** testes para todos os estados e cross-tenant.
**Dependencies:** Task 8
**Files likely touched:** views, serializers, teste
**Estimated scope:** Small

Evidência 2026-09-16: endpoint GET /api/tenders/{id}/processing-status/ implementado;
TenderProcessingStatusSerializer em camelCase expõe tenderId, status, progress, processedChunks e erro seguro;
Retry-After: 2 incluído em PENDING e PROCESSING; cross-tenant retorna 404 seguro;
migration 0003_tender_processed_chunks_tender_progress aplicada;
45 testes pytest passando (6 novos testes em test_tender_management.py); ruff check . e django check limpos.

### Task 12: Implementar extração por página
**Description:** Criar serviço puro para texto e offsets de PDF.
**Acceptance criteria:**
- [x] Fixture textual retorna uma entrada por página.
- [x] PDF sem texto produz erro de domínio.
- [x] Serviço não conhece HTTP/Celery.
**Verification:** `pytest backend/tests/unit/pipeline/test_pdf_extractor.py`.
**Dependencies:** Task 8
**Files likely touched:** `pdf_extractor.py`, erro, fixture, teste
**Estimated scope:** Small

Evidência 2026-09-16: apps.pipeline.pdf_extractor implementado com extract_pdf_pages,
ExtractedPage e normalize_page_text; apps.pipeline.exceptions com códigos PDF_INVALID,
PDF_ENCRYPTED, NO_TEXT_EXTRACTED, PAGE_LIMIT_EXCEEDED e CHAR_LIMIT_EXCEEDED;
testes unitários com fixture textual, em branco, criptografada, corrompida e limites;
7/7 testes unitários passando em backend/tests/unit/pipeline/test_pdf_extractor.py;
52 testes pytest no total passando; ruff check . e django check limpos.

### Task 13: Criar task Celery e chunking
**Description:** Implementar task versionada, estados, chunks com metadados e retry.
**Acceptance criteria:**
- [x] Task recebe `tenderId` e `jobId`.
- [x] Redelivery não duplica chunks.
- [x] Falha final termina em `FAILED`.
- [x] Outbox transacional evita `PENDING` órfão quando RabbitMQ falha.
- [x] Lease/heartbeat recupera `PROCESSING` stale e compare-and-set impede task antiga de sobrescrever estado novo.
- [x] Relay do outbox usa lease, publisher confirm, retry/backoff, DLQ e reconciliação de rows presas.
- [x] Nova geração substitui atomicamente a geração current; falha preserva a geração anterior.
- [x] Outbox relay republica com segurança após crash entre publisher confirm e marcação `SENT`.
**Verification:** teste com worker e fixture PDF.
**Dependencies:** Tasks 10, 11 e 12
**Files likely touched:** `tasks.py`, chunker, models, migration, teste
**Estimated scope:** Medium

Evidência 2026-09-16: task versionada pipeline.process_tender.v1 implementada; modelos DocumentChunk e OutboxMessage
criados e migrados; chunking semântico com preservação de página e offsets code-point em chunker.py; idempotência por jobId;
staged generation swap atômico garantindo que falha preserva a geração anterior; outbox transacional no upload de editais
com relay com lease atômico e reconciliador de timeouts (outbox.py); 59 testes pytest passando no total (7 novos testes em
test_document_pipeline.py); ruff check ., django check e makemigrations --check 100% limpos.

## Checkpoint: Processing contract
- [x] Tasks 11–13 concluídas.
- [x] Status, extração, chunking e redelivery são verificáveis.

## Checkpoint: Ingestion
- [x] Tasks 8–13 concluídas.
- [x] Upload retorna `202` e status evolui corretamente.
- [x] Fixture produz chunks com página e offsets.
- [x] Revisar antes da Fase 3.

## Security preflight

- [x] Revisar [docs/security-threat-model.md](../docs/security-threat-model.md).
- [x] Confirmar que CORS não usa `*` com credenciais e que headers de segurança estão configurados.
- [x] Confirmar `.gitignore` para `.env`, chaves e certificados.
- [x] Confirmar que logs não contêm tokens, senhas, chaves ou PDF integral.
- [x] Confirmar limites de tokens, timeout e validação de respostas de Gemini/Groq.

**Verification:** checklist manual e testes de autenticação, upload, cross-tenant e rate limiting antes da primeira release.

Evidência 2026-09-17: headers de `/health/` e CORS autorizado foram verificados
com `curl`; origem não autorizada não recebeu `access-control-allow-origin`.
`.gitignore` cobre `.env`, chaves, certificados, caches e artefatos de teste;
logs recentes de API/worker não continham credenciais, tokens ou PDF integral.
Os testes de auth, upload, cross-tenant e throttling permanecem verdes. Não há
histórico Git nesta workspace; a verificação de secrets cobre os arquivos
presentes e o workflow repete a varredura em arquivos rastreados.

Evidência adicional 2026-09-16: o preflight de `http://127.0.0.1:3000` foi
reproduzido e corrigido com a lista explícita `FRONTEND_ORIGINS`, compartilhada
por CORS e CSRF. A origem não autorizada continua sem cabeçalho CORS; 115/115
testes backend, Ruff e `manage.py check` passaram após a correção.

## Phase 3 — Vector intelligence and RAG

### Task 14: Criar adapter Gemini Embedding 2
**Description:** Encapsular `google-genai`, formatos de retrieval, dimensão 768 e validação externa.
**Acceptance criteria:**
- [x] Documentos e queries usam formatos documentados.
- [x] Dimensão diferente é rejeitada.
- [x] Chave vem apenas do ambiente.
**Verification:** teste unitário com provider mockado.
**Dependencies:** Task 13
**Files likely touched:** `embeddings.py`, settings, requirements, teste
**Estimated scope:** Medium

Evidência 2026-09-16: GeminiEmbeddingAdapter implementado em apps.intelligence.embeddings;
google-genai 2.23.0 utilizado com EmbedContentConfig(task_type=RETRIEVAL_DOCUMENT/QUERY, output_dimensionality=768);
validação estrita de dimensão (768) rejeita divergências com ValueError; chave de API requerida de GEMINI_API_KEY;
5 testes unitários passando em backend/tests/unit/intelligence/test_embeddings.py; 64 testes pytest no total;
ruff check . e django check limpos.

### Task 15: Persistir chunks e índice HNSW
**Description:** Criar `DocumentChunk`, migration `vector(768)` e índice cosseno.
**Acceptance criteria:**
- [x] Migration habilita pgvector.
- [x] Chunk guarda página, offsets e embedding.
- [x] Índice usa operador cosseno.
- [x] Metadados registram modelo, versão, dimensão, normalização e fingerprint de preprocessing.
- [x] B-tree de tenant e estratégia de overfetch/fallback exato possuem teste de recall.
- [x] Somente chunks `is_current=true` participam da busca.
- [x] Geração `STAGED` não aparece na busca até conclusão atômica.
**Verification:** migration limpa e consulta de vizinhos.
**Dependencies:** Tasks 13 e 14
**Files likely touched:** models, migration, repository, teste
**Estimated scope:** Medium

Evidência 2026-09-16: DocumentChunk estendido com VectorField(768), metadados de embedding e índices;
migration 0002 com VectorExtension() e HnswIndex(vector_cosine_ops, m=16, ef_construction=64) aplicada no PostgreSQL real;
VectorSearchRepository implementado em apps.intelligence.repository; busca semântica por CosineDistance isolada
por tenant e restrita a is_current=true; 70 testes pytest no total (6 novos testes em test_vector_intelligence.py);
ruff check . e django check limpos.

### Task 16: Indexar embeddings na task
**Description:** Conectar chunking ao adapter e persistir em lotes.
**Acceptance criteria:**
- [x] Edital processado cria chunks vetorizados.
- [x] Falha do provider não marca `PROCESSED`.
- [x] Retry não duplica chunks.
**Verification:** integração pipeline/provider mockado.
**Dependencies:** Tasks 13 e 15
**Files likely touched:** pipeline task, intelligence service, teste
**Estimated scope:** Medium

Evidência 2026-09-16: `MockEmbeddingAdapter` e factory `get_embedding_adapter` implementados em
`apps.intelligence.embeddings` (usando GeminiEmbeddingAdapter quando GEMINI_API_KEY está configurada
e MockEmbeddingAdapter determinístico de 768 dimensões para execução local/offline/CI); task Celery
`pipeline.process_tender.v1` atualizada para gerar embeddings em batch e persistir `embedding` de 768
dimensões em cada `DocumentChunk` da geração staged; falhas do provider de embedding abortam a task,
limpam a geração staged e marcam `FAILED` sem promover para `PROCESSED` e sem corromper geração corrente
anterior; 73/73 pytest passando no backend (incluindo testes de sucesso com vetorização, falha de provider
e redelivery idempotente); ruff check ., django check e makemigrations --check 100% limpos.

Evidência adicional 2026-09-16: a cota gratuita do projeto Gemini real foi
esgotada durante a demo (`429 embed_content_free_tier_requests`). O ambiente
local foi colocado em `GEMINI_API_KEY=mock`, o edital afetado foi reencaminhado
e concluiu `PROCESSED` com 224 chunks; o E2E passou sem chamadas externas.

## Checkpoint: Vector foundation
- [x] Tasks 14–16 concluídas.
- [x] Adapter, dimensão 768, migration e indexação passam.

### Task 17: Implementar retrieval e busca semântica
**Description:** Criar serviço e endpoint paginado com filtros e `topK` limitado.
**Acceptance criteria:**
- [x] Query é validada.
- [x] Resultados têm score, página e snippet.
- [x] Nenhum chunk de outro tenant aparece.
- [x] Overfetch iterativo e fallback exato cobrem tenant pequeno, enviesado e vazio.
- [x] `topK` e `pageSize` são limitados a 50 e paginação é testada.
**Verification:** integração com embeddings determinísticos.
**Dependencies:** Task 16
**Files likely touched:** repository, serializers, views, teste
**Estimated scope:** Medium

Evidência 2026-09-16: endpoint `POST /api/search/semantic/` implementado com `SemanticSearchView`
e `SemanticSearchRequestSerializer` em `apps.intelligence`; validação estrita de payload (query não-vazia,
topK máx 50, pageSize máx 50, page >= 1, tenderId validado no tenant); `VectorSearchRepository` atualizado
com overfetch iterativo (`min(top_k * 2, available_count)`), fallback exato forçado (`enable_indexscan = off`,
`enable_bitmapscan = off`) para cobrir tenants pequenos/enviesados/vazios e geração de snippet; paginação
`{ data, pagination }` com `page`, `pageSize`, `totalItems`, `totalPages`; 83/83 pytest passando no backend
(8 novos testes de integração em `test_semantic_search.py` e 2 novos testes de repositório em
`test_vector_intelligence.py`); ruff check ., django check e makemigrations --check 100% limpos; 3/3 vitest limpos.

### Task 18: Criar modelos de conversa e mensagens
**Description:** Persistir conversa vinculada a tenant, usuário e edital.
**Acceptance criteria:**
- [x] Só aceita edital processado do tenant.
- [x] Mensagens preservam ordem e role.
- [x] Dados são isolados.
**Verification:** testes de model e autorização.
**Dependencies:** Task 17
**Files likely touched:** models, migration, serializers, teste
**Estimated scope:** Medium

Evidência 2026-09-16: modelos `Conversation` e `Message` implementados em `apps.conversations.models`;
validação estrita rejeita editais com status diferente de `PROCESSED` e editais pertencentes a outro tenant;
mensagens preservam ordem cronológica e role (`user`/`assistant`) com campo estruturado `citations`;
serializers `MessagePublicSerializer` e `ConversationPublicSerializer` em camelCase; migration
`0001_initial` de conversas aplicada no PostgreSQL real; 89/89 pytest passando no backend (6 novos
testes de integração e serializers em `test_conversation_models.py`); ruff check ., django check e
makemigrations --check 100% limpos; 3/3 vitest limpos.

### Task 19: Implementar serviço e endpoint RAG
**Description:** Recuperar contexto, chamar LLM via LangChain, validar saída e construir citações dos chunks.
**Acceptance criteria:**
- [x] Edital não processado retorna `409`.
- [x] Resposta sem evidência declara insuficiência.
- [x] Citações têm `chunkId`, página, trecho e score.
- [x] IDs citados existem no retrieval e quotes são comparados ao texto persistido.
- [x] Contexto é delimitado como dado não confiável e nenhuma ferramenta é disponibilizada ao modelo.
- [x] Schema de saída é validado; IDs e quotes são allowlisted contra o retrieval.
**Verification:** fixture e teste de grounding.
**Dependencies:** Tasks 17 e 18
**Files likely touched:** conversation service, views, serializers, intelligence, teste
**Estimated scope:** Medium

Evidência 2026-09-16: endpoint `POST /api/tenders/{id}/chat/` implementado com `TenderChatView` em
`apps.conversations.views` e `ChatRequestSerializer`; rejeição com 409 CONFLICT para editais não processados
(PENDING, PROCESSING, FAILED) e 404 para editais de outro tenant; pipeline RAG em `rag_service.py` com
recuperação vetorial por similaridade, delimitação estrita de contexto como dado não confiável
(`<context_document id="..." page="...">`), allowlist de citações contra os chunks recuperados com rejeição
de chunk IDs alucinados e validação de quotes; declaração de insuficiência com mensagem segura quando
não há evidência; mock determinístico para CI/testes offline e suporte a Gemini 2.0 Flash; persistência
de mensagens na conversa; dependência `langchain 0.3.30` adicionada e travada em `uv.lock`; 99/99 pytest
passando no backend (10 novos testes em `test_rag_chat.py`); ruff check ., django check e
makemigrations --check 100% limpos; 3/3 vitest limpos.

## Checkpoint: Retrieval and RAG contract
- [x] Tasks 17–19 concluídas.
- [x] Busca e chat têm filtro de tenant e citação verificável.

## Checkpoint: Intelligence
- [x] Tasks 14–19 concluídas.
- [x] Busca tem score/página e filtro de tenant.
- [x] Chat tem citação verificável.
- [x] Revisar antes da Fase 4.

## Phase 4 — Cache and protection

### Task 20: Adicionar cache de busca
**Description:** Cachear por tenant, query e filtros com namespace versionado.
**Acceptance criteria:**
- [x] Segunda busca equivalente é cache hit.
- [x] Chave inclui tenant.
- [x] TTL é configurável.
**Verification:** teste com Redis.
**Dependencies:** Task 17
**Files likely touched:** cache, settings, views, teste
**Estimated scope:** Small

Evidência 2026-09-16: módulo de cache implementado em `apps.intelligence.cache` com chave canônica
`govintel:v1:semantic:{companyId}:{scope}:{dataRevision}:{embeddingVersion}:{indexVersion}:{sha256(canonicalQuery+filters)}`;
integração em `SemanticSearchView` no Redis; TTL configurável via `SEARCH_CACHE_TTL` (default 300s);
mecanismo de `dataRevision` por tenant permitindo invalidação rápida sem SCAN; 104/104 pytest passando
no backend (5 novos testes em `test_search_cache.py` cobrindo cache hit, isolamento por tenant,
invalidação por data revision e TTL configurável); ruff check ., django check e makemigrations --check
100% limpos; 3/3 vitest limpos.

### Task 21: Implementar invalidação por edital
**Description:** Invalidar resultados quando processamento termina.
**Acceptance criteria:**
- [x] Cache do edital é removido.
- [x] Cache de outro tenant permanece.
**Verification:** integração Redis/pipeline.
**Dependencies:** Tasks 13 e 20
**Files likely touched:** pipeline task, cache, teste
**Estimated scope:** Small

Evidência 2026-09-16: invalidação de cache integrada à task Celery `pipeline.process_tender.v1`
(acionada na conclusão atômica com status `PROCESSED` via `increment_company_data_revision(company_id)`)
e ao endpoint de deleção de edital (`DELETE /api/tenders/{id}/`); novo processamento ou remoção
invalida imediatamente buscas cacheadas do tenant sem afetar o cache de outras empresas;
107/107 pytest passando no backend (3 novos testes em `test_cache_invalidation.py` cobrindo invalidação
na conclusão do worker, preservação do cache de outro tenant e invalidação na deleção); ruff check .,
django check e makemigrations --check 100% limpos; 3/3 vitest limpos.

### Task 22: Configurar throttling
**Description:** Aplicar limites Redis-backed a login, busca e chat.
**Acceptance criteria:**
- [x] Excesso retorna `429` no envelope comum.
- [x] Limites são independentes por usuário/endpoint.
- [x] Detalhes do Redis não vazam.
- [x] Handler global de exceções mantém o envelope comum para `401`, `404`, parser, throttling e `500`.
**Verification:** testes de throttle.
**Dependencies:** Task 20
**Files likely touched:** settings, throttles, urls, teste
**Estimated scope:** Small

Evidência 2026-09-16: classes de throttling implementadas em `apps.core.throttling` (`BaseGovIntelThrottle`,
`LoginThrottle`, `SearchThrottle`, `ChatThrottle`) usando Redis como backend de cache; chaves canônicas
seguindo estritamente `govintel:v1:throttle:{ident}:{endpoint}` (IP para login anônimo, userId para busca e chat);
configuração de taxas em `REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]` dinâmicas e sobrescrevíveis; views integradas:
`LoginView` (5/min), `SemanticSearchView` (30/min) e `TenderChatView` (15/min); excesso retorna 429 com cabeçalho
`Retry-After` e envelope padrão `{ "error": { "code": "RATE_LIMITED", "message": "...", "details": {} } }`; limites
provados independentes por usuário e endpoint; falhas internas e exceções de infraestrutura mascaradas com HTTP 500
`INTERNAL_SERVER_ERROR` sem vazamento de strings de conexão, hosts ou stack traces; `custom_handler404` e `custom_handler500`
registrados em `config.urls`; 114/114 pytest passando no backend (7 novos testes em `test_throttling.py`); ruff check .,
django check e makemigrations --check 100% limpos; 3/3 vitest limpos.

## Checkpoint: Protection
- [x] Tasks 20–22 concluídas.
- [x] Cache hit, invalidação e `429` comprovados.
- [x] Revisar antes da Fase 5.

## Phase 5 — Web application

### Task 23: Criar cliente API e sessão JWT
**Description:** Implementar tipos, cliente HTTP, erros e refresh.
**Acceptance criteria:**
- [x] Cliente segue contratos e não registra tokens.
- [x] Access token armazenado estritamente em memória (sem localStorage/sessionStorage).
- [x] Refresh transparente em 401 com deduplicação de chamadas concorrentes.
- [x] Injeção automática de header CSRF em requisições de mutação (POST, PUT, PATCH, DELETE).
- [x] Envelopes de erro padronizados convertidos em `ApiClientError` sem vazar tokens.
**Verification:** Vitest do cliente.
**Dependencies:** Tasks 5 e 6
**Files likely touched:** `frontend/lib/http.ts`, tipos, auth store, teste
**Estimated scope:** Medium

Evidência 2026-09-16: tipos canônicos de domínio e envelopes definidos em `frontend/lib/types.ts` (`ApiError`,
`User`, `Company`, `AuthResponse`, `Tender`, `ProcessingStatus`, `SearchResultItem`, `Citation`, `Message`, etc.);
gerenciador de autenticação em memória implementado em `frontend/lib/auth.ts` (`authStore`, `getAccessToken`,
`setAccessToken`, `ensureCsrfToken`, `refreshAccessToken`, etc.) garantindo que access token nunca é exposto
em `localStorage` ou `sessionStorage`; cliente HTTP em `frontend/lib/http.ts` (`apiRequest`, `ApiClientError`)
com injeção automática de Bearer token, injeção de CSRF token em mutações, auto-refresh transparente em 401
com deduplicação (single-flight) e retry imediato; 11/11 testes Vitest passando no frontend (8 novos testes em
`tests/auth.test.ts` e 3 em `tests/http.test.ts`); build Next.js de produção passando sem erros; lint e typecheck
100% limpos; 114/114 pytest passando no backend.

### Task 24: Criar telas de registro e login
**Description:** Construir formulários acessíveis e estados de erro.
**Acceptance criteria:** registro/login reais e navegação ao dashboard.
**Verification:** Vitest e verificação manual.
**Dependencies:** Task 23
**Files likely touched:** auth routes, auth components, teste
**Estimated scope:** Medium

Evidência 2026-09-16: formulários acessíveis implementados em `frontend/app/login/page.tsx` e
`frontend/app/register/page.tsx` (`"use client"`, labels vinculados por `htmlFor`, IDs acessíveis);
`authStore.login()` e `authStore.register()` chamados; redirecionamento para `/dashboard` em sucesso;
exibição de erro via `.alert-error`; estilos em `globals.css`; 2 testes de renderização em
`tests/auth-pages.test.tsx` passando; 13/13 vitest passando no total; lint e typecheck limpos;
build de produção inclui `/login` (2.37 kB) e `/register` (2.47 kB) verificados em container running;
`/login` e `/register` retornam 200 em `curl` no container; `vitest.config.mjs` criado com JSX fix
(`oxc: false`, `esbuild` com `jsx: "automatic"`); 114/114 pytest passando no backend.

### Task 25: Criar dashboard e upload com polling
**Description:** Exibir editais, enviar PDF com chave idempotente e acompanhar status.
**Acceptance criteria:** lista paginada e polling termina em sucesso/erro.
**Verification:** componentes com mocks e manual.
**Dependencies:** Tasks 9, 11 e 23
**Files likely touched:** dashboard, tender components, hooks, teste
**Estimated scope:** Medium

Evidência 2026-09-16: módulo `frontend/lib/tenders.ts` criado com `tenderApi.list()` (GET paginado),
`tenderApi.upload()` (POST multipart com `Idempotency-Key`, sem Content-Type manual para preservar boundary),
`tenderApi.getStatus()` (GET status por tenderId) e `generateIdempotencyKey()` (uuid via crypto.randomUUID
com fallback Math.random); função `pollProcessingStatus()` com estados terminais `PROCESSED`/`FAILED`,
callback `onUpdate`, maxAttempts configurável (default 30) e intervalo configurável (default 2000 ms);
page `frontend/app/dashboard/page.tsx` (`"use client"`) com lista paginada de editais, formulário de upload
acessível com labels vinculados (`upload-title`, `upload-description`, `upload-file`), estados de
upload/polling/done/error com `aria-live`, cards de tender com status colorido e links para busca/chat
(somente em PROCESSED), paginação prev/next, botão de logout; estilos adicionados em `globals.css`;
10 novos testes em `tests/dashboard.test.ts` (list, upload com Idempotency-Key, FormData sem Content-Type,
getStatus, generateIdempotencyKey único, poll PROCESSED, poll FAILED, poll timeout); 23/23 vitest passando
no total; lint e typecheck limpos; build de produção inclui `○ /dashboard 3.93 kB` confirmado; 6/6
containers saudáveis após rebuild.

## Checkpoint: Auth and upload UI
- [x] Tasks 23–25 concluídas.
- [x] Sessão, dashboard, upload e polling funcionam com mocks/ API real.

### Task 26: Criar busca semântica
**Description:** Construir formulário, filtros e resultados com score/página/snippet.
**Acceptance criteria:** validação, paginação e estados loading/vazio/erro.
**Verification:** Vitest e manual.
**Dependencies:** Tasks 17 e 25
**Files likely touched:** search route, components, types, teste
**Estimated scope:** Medium

Evidência 2026-09-16: `frontend/lib/search.ts` criado (`searchApi.search` POST
`/api/search/semantic/` omitindo campos opcionais ausentes); página
`frontend/app/search/page.tsx` (`"use client"`) com formulário acessível
(label sr-only `search-query`, filtro `search-tender-filter` com editais
PROCESSED), estados idle/loading/done/error, vazio, resultados com página,
score em % e snippet, paginação prev/next e link para chat por edital;
estilos em `globals.css`; 6 testes em `tests/search.test.ts` (payload com
todos os campos, omissão de opcionais, vazio, erro 400 e 429);
34/34 vitest; lint, typecheck e build passando com rota `○ /search 3.69 kB`.

### Task 27: Criar chat com citações
**Description:** Construir conversa e painel de fontes.
**Acceptance criteria:** chat mostra citação e trata erro, rate limit e ausência de evidência.
**Verification:** Vitest e manual com fixture.
**Dependencies:** Tasks 19 e 26
**Files likely touched:** chat route, components, teste
**Estimated scope:** Medium

Evidência 2026-09-16: `frontend/lib/chat.ts` criado (`chatApi.send` POST
`/api/tenders/{id}/chat/` incluindo conversationId apenas quando fornecido);
página `frontend/app/chat/page.tsx` (`"use client"`, `useSearchParams` em
componente separado envolvido em `<Suspense>` para CSR bailout) com
mensagens user/assistant em `role="log"`, painel de fontes com página/score/
quote, tratamento de 409 (edital não processado), 429 (rate limit) e remoção
de mensagem órfã em erro, Enter para enviar; estilos em `globals.css`;
5 testes em `tests/chat.test.ts` (payload, conversationId, 409, 429, sem
evidência); 34/34 vitest; lint, typecheck e build passando com rota
`○ /chat 3.39 kB`.

### Task 28: Criar teste E2E da demo
**Description:** Automatizar cadastro → upload → processamento → busca → chat.
**Acceptance criteria:** Playwright verifica página e trecho citados.
**Verification:** `npx playwright test e2e/govintel-flow.spec.ts`.
**Dependencies:** Tasks 24–27
**Files likely touched:** E2E spec, fixtures, config
**Estimated scope:** Medium

Evidência 2026-09-16/17: projeto Playwright na raiz (`package.json` com
`@playwright/test`, `playwright.config.ts` com baseURL localhost:3000 e timeout
240s); spec `e2e/govintel-flow.spec.ts` cobrindo cadastro → upload de PDF →
processamento (aguarda status PROCESSED) → busca semântica (snippet) → chat com
citações (página e trecho); fixture `e2e/fixtures/edital-demo.pdf` textual
gerado com o helper dos testes; override `docker-compose.e2e.yml` forçando
`GEMINI_API_KEY=mock` para E2E determinístico/offline; correção de bug de
produção descoberto pelo E2E: `process_outbox_batch()` era chamado dentro de
`transaction.atomic()` no caminho com idempotência, permitindo o worker consumir
a mensagem antes do commit do edital (tender ficava PENDING);
migrado para `transaction.on_commit(process_outbox_batch)`;
`npx playwright test e2e/govintel-flow.spec.ts` passando (5 execuções
consecutivas, com provider real e mock); 114/114 pytest, 34/34 vitest, lint e
typecheck limpos; build Next inclui /search, /chat e /dashboard.

## Checkpoint: Search and chat UI
- [x] Tasks 26–28 concluídas.
- [x] Busca, chat, citações e E2E estão verificáveis.

## Checkpoint: Demo
- [x] Tasks 23–28 concluídas.
- [x] Fluxo completo funciona no navegador.
- [x] Playwright passa em ambiente limpo.

## Phase 6 — Delivery

### Task 29: Consolidar comandos e README
**Description:** Documentar setup, variáveis, migrations, worker, testes e demo.
**Acceptance criteria:** pessoa nova reproduz a demo seguindo README, incluindo storage privado, migrations, fila, outbox relay, fixtures e provider mockado nos testes.
- [x] README descreve setup, variáveis, migrations, storage privado, worker, outbox e testes.
- [x] Roteiro reproduz a demo com fixture e provider mockado.
**Verification:** setup em ambiente limpo.
**Dependencies:** Tasks 1–28
**Files likely touched:** `README.md`, `.env.example`, `docs/demo-script.md`
**Estimated scope:** Medium

Evidência 2026-09-17: README e roteiro foram atualizados e conferidos contra
`docker compose config --quiet`, `docker compose up -d --build --wait`, health
checks, fila declarada, fixture Playwright e override `GEMINI_API_KEY=mock`.
O stack local reproduz o fluxo completo já verificado na Task 28.

Evidência adicional 2026-09-18: README expandido para documentar stack,
arquitetura, fluxo de upload/outbox/Celery, embeddings, RAG, citações,
segurança, configuração, testes, limites e conceitos do projeto; Prettier
passou no arquivo.

### Task 30: Configurar pipeline CI de qualidade
**Description:** Criar pipeline de lint, typecheck, testes, integração, E2E aplicável e builds.
**Acceptance criteria:**
- [x] PR e push para `main` executam todos os gates definidos.
- [x] Falha em qualquer gate deixa pipeline vermelho.
- [x] Banco, Redis e RabbitMQ têm health checks antes dos testes de integração.
**Verification:** execução local equivalente e workflow validado em um PR.
**Dependencies:** Tasks 2, 3, 28 e 29
**Files likely touched:** workflow CI, `pyproject.toml`, `frontend/package.json`
**Estimated scope:** Medium

Evidência 2026-09-17: `.github/workflows/ci.yml` separa lint, typecheck,
testes com cobertura, integração com serviços saudáveis, auditoria, build das
imagens e E2E mockado; qualquer comando falho encerra o job. A execução em
GitHub ficará pendente até existir um remoto, mas os mesmos comandos foram
executados localmente com 114 testes backend, 34 testes frontend e builds
limpos.

## Checkpoint: CI quality
- [x] Tasks 29–30 concluídas.
- [x] README e pipeline executam os mesmos comandos aprovados.

### Task 31: Automatizar auditoria e atualização de dependências
**Description:** Configurar auditoria nativa, lockfiles reprodutíveis e Dependabot/Renovate sem remediation forçada.
**Acceptance criteria:**
- [x] Auditoria nativa roda no CI.
- [x] Lockfiles são usados em instalação imutável.
- [x] Findings críticos/altos alcançáveis não são ignorados.
**Verification:** auditoria local, instalação imutável e revisão do workflow.
**Dependencies:** Task 30
**Files likely touched:** lockfiles, `.github/dependabot.yml`, workflow CI
**Estimated scope:** Medium

Evidência 2026-09-17: `uv sync --locked`, `uv run pip-audit --strict`,
`npm ci --ignore-scripts` e `npm audit --audit-level=high` passaram. A auditoria
encontrou advisories em DRF 3.16, LangChain 0.3 e pypdf 5; as dependências foram
atualizadas para DRF 3.18.1, LangChain 1.4.1 e pypdf 6.19.0, o lockfile foi
regenerado e a suíte backend (114 testes) continuou verde. Dependabot acompanha
raiz, frontend e backend semanalmente; nenhum `audit fix --force` foi usado.

### Task 32: Preparar deploy da demonstração
**Description:** Escolher plataforma e documentar serviços gerenciados, secrets, smoke test e rollback básico.
**Acceptance criteria:**
- [x] Plataforma e limitações estão registradas.
- [x] Imagens são reproduzíveis.
- [x] Deploy não usa secrets no repositório.
- [x] Smoke test e rollback apontam para uma versão anterior.
**Verification:** build das imagens e checklist de deploy.
**Dependencies:** Task 31
**Files likely touched:** Dockerfile, `deploy/`, `docs/deployment.md`
**Estimated scope:** Medium

Evidência 2026-09-17: Render foi escolhido e registrado em
`docs/deployment.md` e `docs/decisions/ADR-001-render-demo.md`, incluindo
Postgres/pgvector, Redis, RabbitMQ, secrets, health check, smoke test e
rollback. `backend/Dockerfile` aceita `PORT` e as imagens API/worker foram
reconstruídas com `uv.lock`; o build Next foi verificado sem warnings de root
de lockfiles após configurar `outputFileTracingRoot`. A limitação de volume
privado compartilhado está explícita: produção exige storage S3-compatible.

## Final Checkpoint

- [x] Todas as tasks concluídas localmente até a preparação de deploy.
- [x] Todos os critérios de [SPEC.md](../SPEC.md) atendidos no escopo do MVP local.
- [x] Cada módulo tem evidência de verificação.
- [x] Spec, plano e tarefas refletem decisões finais.
- [ ] Revisão humana concluída antes de merge ou deploy.

Evidência 2026-09-17: Tasks 1–32 e checkpoints de produto, segurança, CI,
auditoria e entrega têm evidência em `context.md` e `memory.md`. A revisão
humana, configuração de required checks em um remoto e qualquer publicação
continuam como próximo gate operacional.

## Pós-demo — qualidade de busca e chat (2026-09-17)

- [x] Diagnosticar extração: editais processados atuais sem chunks vazios ou embeddings ausentes.
- [x] Reranking lexical híbrido e snippets centrados no termo da consulta.
- [x] Resposta mock do RAG limitada às frases pertinentes e insuficiência para match fraco.
- [x] Citações com `quote` alinhadas ao frontend, mantendo `text` temporariamente.
- [x] Adapter Gemini Embedding 2 alinhado à SPEC (instruções em `contents`, sem `task_type`).
- [x] Regressões e gates: 118 pytest, Ruff, Django check, Compose config, E2E 1/1 e Vitest 34/34.

Evidência: execução local concluída em 2026-09-17; nenhum deploy ou push realizado.

## Pós-demo — OCR e citações (2026-09-17)

- [x] OCR local para páginas escaneadas: páginas sem camada de texto são
  rasterizadas (pypdfium2) e reconhecidas com Tesseract (`por`), com fallback
  gracioso para `NO_TEXT_EXTRACTED` quando o toolchain ausente ou `OCR_ENABLED=false`.
- [x] Citações sem campo legado: saída apenas com `quote`; `text` removido de
  `validate_citations` e do mapeamento da resposta do LLM; testes atualizados.
- [x] Dependências travadas (pypdfium2, pytesseract, pillow), Tesseract + pacote
  português no Dockerfile e nos jobs backend do CI.
- [x] Gates: 124 pytest, Ruff, Django check, makemigrations --check, 34 Vitest,
  lint/typecheck frontend, E2E Playwright 1/1.

Evidência: execução local concluída em 2026-09-17; nenhuma alteração de contrato
público — `Citation` do frontend já consumia apenas `quote`.

## Pós-demo — estabilização de sessão, CI e chat real (2026-09-17)

- [x] CSRF, rotação/reuse de refresh e throttling de cadastro, refresh e upload
  corrigidos; Redis indisponível falha fechado.
- [x] Traversal de storage bloqueado e mensagens internas do pipeline sanitizadas.
- [x] Pillow atualizado para 12.3.0; `pip-audit --strict` sem vulnerabilidades.
- [x] CI provisiona PostgreSQL, Redis e RabbitMQ com health checks.
- [x] Metadados de embedding persistidos, retrieval isolado por provider e
  comando `reindex_embeddings` criado.
- [x] 29 editais reindexados em OpenRouter; 55 chunks atuais homogêneos.
- [x] Citações fail-closed com uma tentativa corretiva; sem prova literal a
  resposta permanece em insuficiência de evidência.
- [x] Gates finais: 151 pytest, 42 Vitest, lint/typecheck, Ruff, Django check,
  migrations check, Compose config, pip-audit e worker ping.
- [x] Chat real após reindexação retornou resposta com 6 citações verificadas.

Pendentes fora deste gate: caller periódico do outbox/reconciliador, storage
compartilhado para múltiplas réplicas, issuer/audience dedicados no JWT e revisão
humana antes de merge/deploy.

## Correção pós-demo — CSRF entre hosts locais (2026-09-17)

- [x] Reproduzir o 403 ao usar frontend em `127.0.0.1` e API configurada em
  `localhost`.
- [x] Alinhar automaticamente o hostname local da API ao hostname da página.
- [x] Adicionar regressão Playwright para cadastro e login nos dois hosts.
- [x] Validar com 43 testes frontend, lint/typecheck, build e 4 testes E2E de
  CSRF; nenhum dado de conta foi criado durante a regressão.

## Redesign frontend — 2026-09-17

- [x] Criar briefing e guias de revisão em `docs/frontend/`.
- [x] Aplicar tokens, tipografia, contraste, foco, responsividade e reduced
  motion sem remover contratos de tela.
- [x] Atualizar home, autenticação, dashboard, busca e chat com estados visuais
  consistentes e foco em evidência/citações.
- [x] Validar navegador real depois do rebuild do frontend.
- [x] Executar testes existentes, lint/Prettier, typecheck e build.
- [x] Salvar evidências PNG das rotas públicas e estados vazios em
  `docs/frontend/evidence/`.
- [ ] Revisão humana em viewport móvel e fluxo autenticado com dados reais de
  demonstração.

## Migração OpenCode + embeddings locais — 2026-09-18

- [x] Separar configuração de LLM e embeddings, sem fallback implícito.
- [x] Implementar adapter local E5 768D com prefixos, batch, L2, cache e
  fingerprint; manter providers legados explícitos.
- [x] Exigir identidade completa do espaço vetorial no retrieval e cache.
- [x] Implementar reindexação staged corpus-wide, promoção atômica e rollback
  por geração.
- [x] Adicionar testes focados para seleção, erros OpenCode, grounding e
  preservação de geração current.
- [x] Rebuild do Compose e `reindex_embeddings --dry-run` na base local;
  evidência 2026-09-18: 29 editais, 55 chunks, 0,03 s.
- [x] Executar reindexação local real e registrar contagens/duração;
  evidência 2026-09-18: 29 editais, 55→55 chunks, 88,88 s, 55 current
  homogêneos no banco.
- [x] Atualizar o modelo de chat para `deepseek-v4-flash`; evidência
  2026-09-18: Compose rebuild, teste focado (10), suíte backend (167), Ruff e
  Django check passaram.
