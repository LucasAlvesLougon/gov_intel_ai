# Memory

## Decisions
- [2026-09-16] Decisão: executar infraestrutura em subetapas verificáveis.
  - Motivo: Task 1 depende dos scaffolds declarados nas Tasks 2–3.
  - Evidência: tasks/todo.md e docs/ci-cd-contract.md; decisão detalhada em docs/implementation-decisions.md.
  - Impacto: configuração e serviços de dados primeiro; gate completo permanece obrigatório antes de identity-tenant.

## Completed
- [2026-09-16] Task: inspeção e preparação do contexto.
  - Alterações: AGENTS.md, context.md, memory.md.
  - Verificação: leitura dos 18 documentos solicitados; diretório sem Git/manifests/lockfiles.

## Lessons
- [2026-09-16] Descoberta: Docker CLI instalado não significa engine pronto; engine Linux passou a responder após tentativa de início do Docker Desktop.

## Open Risks
- [2026-09-16] Risco: ainda não há aplicação executável nem testes.
  - Mitigação: concluir e verificar checkpoint Tasks 1–3 antes do schema de domínio.

## Completed — 2026-09-16, scaffold backend
- [2026-09-16] Task: Task 1 parcial e Task 2 verificada.
  - Alterações: Compose de seis serviços, .env.example/.gitignore; Django/Celery,
    health com consulta real, declaração durável de filas/DLQ, uv.lock e Dockerfile.
  - Verificação: Compose config; cinco serviços saudáveis; SQL PostgreSQL 16.15,
    vector 0.8.6 disponível, Redis PONG, Celery pong; 5 pytest passaram;
    Ruff e manage.py check sem problemas. Frontend ainda pendente.

## Decisions — 2026-09-16, runtimes
- [2026-09-16] Decisão: Python 3.12.14/Django 5.2.17/Celery 5.6.3, dependências em uv.lock.
  - Motivo: Django LTS e compatibilidade da stack; instalação imutável.
  - Evidência: resolução uv e build Docker; https://docs.djangoproject.com/en/5.2/;
    https://docs.celeryq.dev/en/stable/django/first-steps-with-django.html;
    https://docs.astral.sh/uv/guides/integration/docker/.
  - Impacto: auth/blacklist serão habilitados junto do User customizado na Task 4,
    evitando migrations prematuras de auth.User; relay/outbox permanece Task 13.

## Open Risks — 2026-09-16, cadastro
- [2026-09-16] Risco: HTTP 409 para email existente permite enumeração no cadastro.
  - Mitigação: pergunta enviada ao usuário; continuar infraestrutura independente,
    sem implementar contrato de cadastro contraditório até resposta.

## Decisions — 2026-09-16, exceção aprovada
- [2026-09-16] Decisão: manter HTTP 409 genérico no cadastro do MVP.
  - Motivo: resolução explícita do conflito entre spec e não enumeração.
  - Evidência: resposta do usuário à pergunta de contrato nesta sessão.
  - Impacto: exceção de inferência no cadastro documentada na threat model;
    login/refresh continuam genéricos; não adicionar confirmação por email.

## Completed — 2026-09-16, checkpoint infraestrutura
- [2026-09-16] Task: Tasks 1–3 verificadas.
  - Alterações: scaffold Next 15, TypeScript, cliente HTTP, lockfile npm,
    Dockerfile non-root, página inicial e README operacional inicial.
  - Verificação: seis serviços saudáveis após restart preservando volumes;
    health API 200; build sem API; next dev 200; 5 pytest e 3 Vitest;
    Ruff/ESLint/Prettier/typecheck; auditoria npm zero; navegador desktop/320px
    e console sem erros. Git ausente, portanto nenhum commit realizado.

## Lessons — 2026-09-16, infraestrutura
- [2026-09-16] Descoberta: Docker network internal neste ambiente impede
  publicação das portas de dados; usar bridge e bind explícito 127.0.0.1.
- [2026-09-16] Descoberta: imagens non-root precisam diretórios de cache/artefatos
  graváveis para comandos de verificação; next build não gera necessariamente
  tsconfig.tsbuildinfo na raiz. Corrigido ownership sem elevar usuário runtime.
- [2026-09-16] Descoberta: NEXT_PUBLIC_* é incorporada no build; URL pública
  passada como build arg. Não passar credenciais em build args.

## Completed — 2026-09-16, Task 4 (Company e User)
- [2026-09-16] Task: Task 4 verificada.
  - Alterações: backend/apps/core/models.py, admin.py, apps.py, backends.py;
    backend/config/settings.py (AUTH_USER_MODEL, django.contrib.auth, token_blacklist,
    AUTHENTICATION_BACKENDS); migration 0001_initial.py; backend/pyproject.toml
    (extend-exclude migrations no ruff).
  - Verificação: 10 pytest passaram (5 novos em test_identity_models.py cobrindo
    UUID, role OWNER, slug único autogerado, Lower unique constraint e NOT NULL company);
    makemigrations --check sem pendências; ruff check . sem erros; django check sem avisos.

## Completed — 2026-09-16, Task 5 (Registro transacional)
- [2026-09-16] Task: Task 5 verificada.
  - Alterações: backend/apps/core/services.py (register_company_and_owner com @transaction.atomic),
    exceptions.py (custom_exception_handler no envelope comum, ConflictError),
    serializers.py (RegisterInputSerializer, UserPublicSerializer, CompanyPublicSerializer),
    views.py (RegisterView), jwt_utils.py (get_tokens_for_user, set_refresh_cookie, clear_refresh_cookie),
    urls.py, backend/config/urls.py (/api/auth/), backend/config/settings.py (REST_FRAMEWORK, SIMPLE_JWT).
  - Verificação: 14 pytest passaram (4 novos em tests/integration/test_identity_tenant.py cobrindo
    registro 201 com refresh cookie protegido, 409 CONFLICT com mensagem genérica aprovada sem persistir
    empresa órfã, rollback transacional atômico em falha e validação 400); ruff check . limpo;
## Completed — 2026-09-16, Task 6 (JWT, refresh e /me/) e Checkpoint Authentication contract
- [2026-09-16] Task: Task 6 e Checkpoint Authentication contract verificados.
  - Alterações: backend/apps/core/views.py (CsrfView, LoginView, TokenRefreshView, LogoutView, MeView),
    serializers.py (LoginInputSerializer), urls.py (csrf, token, token/refresh, logout, me),
    tests/integration/test_identity_tenant.py (testes cobrindo login com credencial válida e inválida,
    não enumeração de email, usuário inativo 401, rotação e blacklist de refresh, reuse detection, logout
    204 com remoção de cookie, /me com Bearer token e csrf).
  - Verificação: 23 pytest passaram (9 novos testes de integração); ruff check . sem erros;
    django check sem avisos; todos os 6 containers Docker continuam saudáveis.

## Completed — 2026-09-16, Task 7 (Permissão e isolamento cross-tenant) e Checkpoint Foundation
- [2026-09-16] Task: Task 7 e Checkpoint Foundation verificados.
  - Alterações: backend/apps/core/permissions.py (get_user_company, filter_by_tenant, IsTenantMember),
    backend/tests/integration/test_identity_tenant.py (test_tenant_isolation_two_companies_cannot_access_or_impersonate,
    test_tenant_helpers_reject_unauthenticated).
  - Verificação: 25 pytest passaram no backend; 3 Vitest passaram no frontend;
    docker compose ps com 6 serviços saudáveis (db, redis, rabbitmq, api, worker, frontend);
    ruff check . limpo; django check limpo; npm lint e tsc limpos.
  - Próximo passo: Revisão humana do Checkpoint Foundation antes de iniciar a Fase 2 (Tenders & Pipeline).

## Completed — 2026-09-16, Task 8 (Modelo e listagem de Tender)
- [2026-09-16] Task: Task 8 verificada após autorização do usuário para iniciar a Fase 2.
  - Alterações: backend/apps/tenders/apps.py, models.py (Tender com UUID, status PENDING/PROCESSING/PROCESSED/FAILED
    e CheckConstraint, company FK com CASCADE, storage_key, original_filename, file_size, sha256, pipeline_generation),
    serializers.py (TenderPublicSerializer em camelCase), views.py (TenderListCreateView paginado com filtros e
    ordenação, TenderDetailView isolado por tenant), urls.py (/api/tenders/), migration 0001_initial de tenders;
    backend/tests/integration/test_tender_management.py.
  - Verificação: 31 pytest passaram (6 novos testes de integração de tenders cobrindo model, constraints,
    listagem por tenant, paginação {data, pagination}, filtro de status, ordenação e 404 cross-tenant);
    ruff check . limpo; django check limpo; makemigrations --check sem alterações pendentes.

## Completed — 2026-09-16, Task 9 (Implementar upload e validação de PDF)
- [2026-09-16] Task: Task 9 verificada.
  - Alterações: backend/apps/tenders/storage.py (LocalStorageAdapter e get_storage_adapter, isolando armazenamento
    privado por {company_id}/{tender_id}.pdf em UPLOAD_ROOT), validators.py (validate_pdf_upload conferindo tamanho
    máximo, não vazio, magic bytes b'%PDF-', cálculo de sha256), views.py (upload POST retornando 202 com status PENDING
    e DELETE 204 com remoção física de blob); backend/tests/integration/test_tender_management.py.
  - Verificação: 36 pytest passaram (5 novos testes de integração de upload e delete cobrindo multipart válido 202,
    arquivo vazio 400, arquivo falso 400, remoção autorizada do blob e rejeição cross-tenant 404); ruff check . limpo;
    django check sem pendências.

## Completed — 2026-09-16, Task 10 (Idempotência do upload) e Checkpoint Upload contract
- [2026-09-16] Task: Task 10 e Checkpoint Upload contract verificados.
  - Alterações: backend/apps/tenders/models.py (modelo IdempotencyKey com UniqueConstraint por company, user, endpoint e key, status_code, response_data, request_hash),
    backend/apps/tenders/views.py (cálculo de request_hash canônico independente do multipart boundary, select_for_update atômico, retorno 202 com mesmo edital em retry idêntico, 422 UnprocessableEntityError se payload divergir com mesma chave, persistência atômica da chave),
    backend/apps/core/exceptions.py (UnprocessableEntityError com code UNPROCESSABLE_ENTITY e HTTP 422),
    migration 0002_idempotencykey aplicada; backend/tests/integration/test_tender_management.py.
  - Verificação: 39 pytest passaram (14 em test_tender_management.py, cobrindo retry reproduzindo mesmo edital, payload divergente com 422 e isolamento multi-tenant da chave de idempotência);
    makemigrations --check sem alterações pendentes; ruff check . sem erros; django check sem avisos.
  - Checkpoint Upload contract (Tasks 8–10) concluído com sucesso.

## Completed — 2026-09-16, Task 11 (Endpoint de status de processamento)
- [2026-09-16] Task: Task 11 verificada.
  - Alterações: backend/apps/tenders/models.py (adicionados campos progress e processed_chunks a Tender),
    backend/apps/tenders/serializers.py (TenderProcessingStatusSerializer em camelCase com tenderId, status, progress, processedChunks, error),
    backend/apps/tenders/views.py (TenderProcessingStatusView com Retry-After: 2 para PENDING e PROCESSING, isolamento por tenant),
    backend/apps/tenders/urls.py (/api/tenders/<uuid:id>/processing-status/),
    migration 0003_tender_processed_chunks_tender_progress aplicada no PostgreSQL real;
    backend/tests/integration/test_tender_management.py (6 novos testes cobrindo PENDING, PROCESSING, PROCESSED, FAILED com erro seguro, cross-tenant 404 e não autenticado 401).
  - Verificação: 45 pytest passaram no backend; 3 Vitest passaram no frontend;
    makemigrations --check sem alterações pendentes; ruff check . sem erros; django check sem pendências.

## Completed — 2026-09-16, Task 12 (Extração textual por página)
- [2026-09-16] Task: Task 12 verificada.
  - Alterações: backend/apps/pipeline/exceptions.py (PipelineDomainError, PdfInvalidError, PdfEncryptedError, NoTextExtractedError, PageLimitExceededError, CharLimitExceededError),
    backend/apps/pipeline/pdf_extractor.py (extract_pdf_pages, ExtractedPage, normalize_page_text; sem dependências de HTTP/Celery),
    backend/tests/fixtures/pdf_helpers.py (create_minimal_text_pdf, create_blank_pdf, create_encrypted_pdf),
    backend/pyproject.toml e uv.lock (dependência pypdf>=5.0.0 instalada em api e worker),
    backend/tests/unit/pipeline/test_pdf_extractor.py (7 testes unitários cobrindo extração multi-página com offsets, PDF sem texto, criptografado, corrompido, limite de páginas, limite de caracteres e ausência de HTTP/Celery).
  - Verificação: 52 pytest passaram no backend; 3 Vitest no frontend; ruff check ., django check e makemigrations --check 100% limpos.

## Completed — 2026-09-16, Task 13 (Task Celery, chunking, outbox transacional) e Checkpoints Processing contract / Ingestion
- [2026-09-16] Task: Task 13, Checkpoint Processing contract e Checkpoint Ingestion verificados.
  - Alterações: backend/apps/tenders/models.py (processing_job_id e processing_lease_until em Tender),
    backend/apps/pipeline/models.py (OutboxMessage com lease atômico, status PENDING/PROCESSING/SENT/FAILED e payload JSON; DocumentChunk com UniqueConstraint(tender, generation, chunk_index), página, offsets, hash e flags staged/is_current),
    backend/apps/pipeline/chunker.py (create_chunks_from_pages com ChunkPayload, chunk_size=800, overlap=100 e offsets code-point),
    backend/apps/pipeline/tasks.py (pipeline.process_tender.v1 com validação de tenant a partir do banco, leitura em storage privado, idempotência por jobId, lease atômico, bulk_create de chunks staged e compare-and-set com atomic swap de geração; descarte de staged chunks em falhas),
    backend/apps/pipeline/outbox.py (schedule_tender_processing, process_outbox_batch com select_for_update(skip_locked=True) e publisher confirm, reconcile_stale_processing_tenders tratando leases expirados com PROCESSING_TIMEOUT),
    backend/apps/tenders/views.py (upload de PDF cria OutboxMessage atomicamente e aciona processamento),
    backend/apps/tenders/storage.py (read_bytes e alias read),
    migrations 0004_tender_processing_job_id_and_more e pipeline 0001_initial aplicadas no PostgreSQL real;
    backend/tests/integration/test_document_pipeline.py (7 testes cobrindo processamento com criação de chunks, redelivery idempotente sem duplicação, PDF corrompido para FAILED, preservação da geração anterior em falha staged, criação transacional de outbox no upload, outbox relay com lease e recuperação por reconciliador).
  - Verificação: 59 pytest passaram no backend; 3 Vitest no frontend; ruff check ., django check e makemigrations --check 100% limpos.
  - Checkpoints: Processing contract e Ingestion concluídos com sucesso. Fase 2 (Tender ingestion and pipeline) 100% finalizada.

## Completed — 2026-09-16, Task 14 (Adapter Gemini Embedding 2 via google-genai)
- [2026-09-16] Task: Task 14 verificada.
  - Alterações: backend/apps/intelligence/embeddings.py (GeminiEmbeddingAdapter utilizando SDK oficial google-genai, formatos documentados RETRIEVAL_DOCUMENT com título e texto e RETRIEVAL_QUERY, validação obrigatória da dimensão 768 e rejeição de discrepâncias com ValueError, leitura de GEMINI_API_KEY do ambiente),
    backend/apps/intelligence/apps.py,
    backend/pyproject.toml e uv.lock (dependências google-genai 2.23.0 e pgvector 0.5.0 instaladas e travadas em api e worker),
    backend/tests/unit/intelligence/test_embeddings.py (5 testes unitários cobrindo RETRIEVAL_DOCUMENT, RETRIEVAL_QUERY, rejeição de dimensão divergente, obrigatoriedade de API key e batching).
  - Verificação: 64 pytest passaram no backend; 3 Vitest no frontend; ruff check ., django check e makemigrations --check 100% limpos.

## Completed — 2026-09-16, Task 15 (Persistência de chunks, pgvector 768 e índice HNSW)
- [2026-09-16] Task: Task 15 verificada.
  - Alterações: backend/apps/pipeline/models.py (VectorField(768), metadados embedding_model_name, embedding_model_version, embedding_dimensions, normalization, preprocessing_fingerprint; índice B-tree doc_chunk_comp_curr_idx e índice HNSW doc_chunk_embedding_hnsw_idx com vector_cosine_ops),
    migration 0002_documentchunk_embedding_and_more com VectorExtension() aplicada no PostgreSQL real;
    backend/apps/intelligence/repository.py (VectorSearchRepository com busca semântica por CosineDistance, isolamento por tenant, exclusão estrita de staged chunks e filtro opcional por edital);
    backend/tests/integration/test_vector_intelligence.py (6 testes de integração cobrindo criação com vetor 768, isolamento por tenant, exclusão de staged chunks, ordenação por similaridade de cosseno, filtro por edital e busca em tenant vazio).
  - Verificação: 70 pytest passaram no backend; 3 Vitest no frontend; ruff check ., django check e makemigrations --check 100% limpos.

## Completed — 2026-09-16, Task 16 (Indexação de embeddings na task) e Checkpoint Vector foundation
- [2026-09-16] Task: Task 16 e Checkpoint Vector foundation verificados.
  - Alterações: backend/apps/intelligence/embeddings.py (MockEmbeddingAdapter gerando vetores determinísticos normalizados de 768 dimensões com interface compatível para ambientes offline/CI; get_embedding_adapter factory lendo GEMINI_API_KEY do ambiente ou retornando mock),
    backend/apps/pipeline/tasks.py (integração do process_tender_v1 com get_embedding_adapter, geração em batch de embeddings de 768 dimensões e atribuição a cada DocumentChunk da geração staged; abort e descarte atômico de staged chunks em falhas do provider mantendo geração anterior intacta e marcando status FAILED),
    backend/tests/unit/intelligence/test_embeddings.py (2 novos testes unitários cobrindo determinismo e interface do MockEmbeddingAdapter e factory get_embedding_adapter),
    backend/tests/integration/test_document_pipeline.py (test_process_tender_success_creates_chunks_and_updates_status verificando vetor 768 em todos os chunks; test_process_tender_provider_failure_does_not_mark_processed verificando abort de task e descarte de staged chunks em falhas do provider de embedding).
  - Verificação: 73 pytest passaram no backend; 3 Vitest no frontend; ruff check ., django check e makemigrations --check 100% limpos.
  - Checkpoint Vector foundation (Tasks 14–16) concluído com sucesso.
## Completed — 2026-09-16, Task 17 (Implementar retrieval e busca semântica)
- [2026-09-16] Task: Task 17 verificada.
  - Alterações: backend/apps/intelligence/serializers.py (SemanticSearchRequestSerializer com validação de query obrigatória, topK com default 8 e máx 50, pageSize com default 20 e máx 50, page >= 1, tenderId opcional),
    backend/apps/intelligence/views.py (SemanticSearchView em POST /api/search/semantic/ com autenticação Bearer, isolamento por tenant derivado de request.user, verificação de tenderId pertencente ao tenant com 404 seguro, geração de query vector e paginação { data, pagination }),
    backend/apps/intelligence/repository.py (VectorSearchRepository com overfetch iterativo de até min(top_k * 2, available_count), fallback exato com SET LOCAL enable_indexscan = off para cobrir tenants pequenos ou enviesados, e geração do campo snippet truncado em 200 caracteres),
    backend/apps/intelligence/urls.py e backend/config/urls.py (/api/search/semantic/),
    backend/tests/integration/test_semantic_search.py (8 testes de integração cobrindo autenticação 401, validação de query 400, validação de limites de topK/pageSize/page 400, validação de tenderId 400/404, retorno completo com score/page/snippet 200, isolamento cross-tenant rigoroso, paginação e tenant vazio),
    backend/tests/integration/test_vector_intelligence.py (2 novos testes cobrindo tenant pequeno e tenant enviesado com snippets).
## Completed — 2026-09-16, Task 18 (Criar modelos de conversa e mensagens)
- [2026-09-16] Task: Task 18 verificada.
  - Alterações: backend/apps/conversations/apps.py (ConversationsConfig),
    backend/apps/conversations/models.py (modelo Conversation com UUID, company, user, tender, validação clean/save de que edital é PROCESSED e pertence ao tenant, índices B-tree company-user e tender-company; modelo Message com UUID, conversation, role user/assistant, content, citations JSONField, ordering por created_at e índice conversation-created_at),
    backend/apps/conversations/serializers.py (MessagePublicSerializer e ConversationPublicSerializer em camelCase),
    migration 0001_initial de conversations gerada e aplicada no PostgreSQL real,
    backend/tests/integration/test_conversation_models.py (6 testes cobrindo criação com edital processado, rejeição de edital pendente 400/ValidationError, rejeição de edital de outro tenant, preservação de ordem cronológica e role de mensagens, isolamento cross-tenant e formatação em camelCase pelos serializers).
## Completed — 2026-09-16, Task 19 (Implementar serviço e endpoint RAG) e Checkpoints Retrieval/RAG contract & Intelligence
- [2026-09-16] Task: Task 19, Checkpoint Retrieval and RAG contract e Checkpoint Intelligence verificados.
  - Alterações: backend/apps/conversations/rag_service.py (process_rag_chat, validate_citations com allowlist estrita contra chunks recuperados e verificação de quotes, MockRAGService determinístico para CI/testes com declaração de insuficiência segura quando não há evidência, LangChainRAGService com delimitação de contexto em <context_document> como dados não confiáveis sem execução de ferramentas, get_rag_service factory),
    backend/apps/conversations/serializers.py (ChatRequestSerializer com validação de message e conversationId opcional),
    backend/apps/conversations/views.py (TenderChatView em POST /api/tenders/{id}/chat/ com validação de status PROCESSED com 409 CONFLICT para não-processados, 404 para tender/conversa de outro tenant, criação automática ou continuação de conversa),
    backend/apps/tenders/urls.py (rota /api/tenders/<uuid:id>/chat/),
    backend/pyproject.toml e uv.lock (dependência langchain 0.3.30 instalada e sincronizada em api e worker),
    backend/tests/integration/test_rag_chat.py (10 testes cobrindo autenticação 401, rejeição de edital não processado 409, rejeição cross-tenant 404, validação de payload 400, validação de conversationId 400/404, autocriação de conversa 200, resposta fundamentada com citação verificável 200, declaração de insuficiência por ausência de evidência, continuidade de conversa com append e rejeição de citações com IDs alucinados ou quotes divergentes).
  - Verificação: 99 pytest passaram no backend; 3 Vitest no frontend; ruff check ., django check e makemigrations --check 100% limpos.
## Completed — 2026-09-16, Task 20 (Adicionar cache de busca)
- [2026-09-16] Task: Task 20 verificada.
  - Alterações: backend/apps/intelligence/cache.py (generate_semantic_search_cache_key com chave canônica versionada govintel:v1:semantic:{companyId}:{scope}:{dataRevision}:{embeddingVersion}:{indexVersion}:{sha256}, get_company_data_revision, increment_company_data_revision, get_search_cache, set_search_cache),
    backend/config/settings.py (adicionada configuração SEARCH_CACHE_TTL com default de 300s),
    backend/apps/intelligence/views.py (SemanticSearchView integrado com verificação de cache e população em cache miss),
    backend/tests/integration/test_search_cache.py (5 testes cobrindo chave canônica por contrato, reprodução idêntica com cache hit sem chamada ao repositório, isolamento estrito de cache entre empresas, invalidação imediata por incremento de data revision do tenant e TTL configurável).
  - Verificação: 104 pytest passaram no backend; 3 Vitest no frontend; ruff check ., django check e makemigrations --check 100% limpos.

## Completed — 2026-09-16, Task 21 (Implementar invalidação por edital)
- [2026-09-16] Task: Task 21 verificada.
  - Alterações: backend/apps/pipeline/tasks.py (integração de `increment_company_data_revision` na conclusão atômica com status `PROCESSED` de editais),
    backend/apps/tenders/views.py (integração de `increment_company_data_revision` no endpoint `DELETE /api/tenders/{id}/`),
    backend/tests/integration/test_cache_invalidation.py (3 testes cobrindo invalidação após término do processamento pelo worker, preservação total de cache de outros tenants e invalidação imediata após deleção do edital via API).
  - Verificação: 107 pytest passaram no backend; 3 Vitest no frontend; ruff check ., django check e makemigrations --check 100% limpos.

## Completed — 2026-09-16, Task 22 (Configurar throttling) e Checkpoint Protection
- [2026-09-16] Task: Task 22 e Checkpoint Protection verificados.
  - Alterações: backend/apps/core/throttling.py (BaseGovIntelThrottle, LoginThrottle, SearchThrottle, ChatThrottle usando Redis como backend de cache; namespace canônico govintel:v1:throttle:{ident}:{endpoint}; resolução dinâmica de taxas e resiliência fail-open para evitar DoS por indisponibilidade transitória do cache),
    backend/config/settings.py (REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] com login: 5/minute, search: 30/minute, chat: 15/minute parametrizáveis por variáveis de ambiente),
    backend/apps/core/exceptions.py (custom_exception_handler atualizado para cobrir 429 RATE_LIMITED com header Retry-After, 400 com normalização de ParseError, mascaramento de 500 sem vazamento de strings de conexão, hosts ou stack traces, e handlers customizados custom_handler404 e custom_handler500),
    backend/config/urls.py (registro de handler404 e handler500),
    backend/apps/core/views.py (LoginView com LoginThrottle),
    backend/apps/intelligence/views.py (SemanticSearchView com SearchThrottle),
    backend/apps/conversations/views.py (TenderChatView com ChatThrottle),
    backend/tests/integration/test_throttling.py (7 testes de integração cobrindo chave canônica por contrato, acionamento de 429 no envelope comum em login, busca e chat com Retry-After, independência estrita de limites por usuário e por endpoint, mascaramento de erros 500 sem vazamento de credenciais Redis, e mapeamento consistente de códigos de status 401, 404 e 400 parser).
  - Verificação: 114 pytest passaram no backend; 3 Vitest no frontend; ruff check . sem erros; django check sem pendências; makemigrations --check limpo; containers saudáveis.
  - Checkpoint Protection (Tasks 20–22) concluído com sucesso. Fase 4 (Cache and protection) 100% finalizada.

## Completed — 2026-09-16, Task 23 (Criar cliente API e sessão JWT)
- [2026-09-16] Task: Task 23 verificada.
  - Alterações: frontend/lib/types.ts (interfaces canônicas de domínio, envelopes de erro ApiError e ApiErrorResponse, paginação, usuários, empresas, editais, status de pipeline, busca semântica e citações),
    frontend/lib/auth.ts (gerenciador de autenticação estritamente em memória com inMemoryAccessToken, inMemoryUser, inMemoryCompany, inMemoryCsrfToken; helpers getAccessToken, setAccessToken, ensureCsrfToken, refreshAccessToken com proteção de single-flight/mutex contra race condition e reúso; authStore com register, login, logout e fetchMe),
    frontend/lib/http.ts (classe ApiClientError com statusCode, code e details; cliente apiRequest com injeção de Bearer token, injeção automática de header X-CSRFToken em métodos de mutação, interceptação de 401 com auto-refresh transparente e retry imediato; desserialização segura de erro em ApiClientError sem expor credenciais em traces),
    frontend/.dockerignore e backend/.dockerignore (isolamento de node_modules, .next, .venv e caches dos contextos de build do Docker),
    frontend/tests/auth.test.ts (8 testes unitários e de integração cobrindo retenção estrita em memória, injeção de Bearer, injeção de CSRF em mutações, parse de envelopes de erro, auto-refresh transparente em 401 com retry, cleanup de sessão em falha de refresh, ausência de tokens em strings de erro e métodos de authStore).
  - Verificação: 11 Vitest passando no frontend; build de produção do Next.js passando com sucesso; lint e typecheck 100% limpos; 114 pytest passando no backend; 6 containers saudáveis.

## Completed — 2026-09-16, Task 24 (Criar telas de registro e login)
- [2026-09-16] Task: Task 24 verificada.
  - Alterações: frontend/app/login/page.tsx e frontend/app/register/page.tsx (formulários acessíveis, labels linkados,
    authStore.login/register, redirecionamento /dashboard, exibição de erro via alert-error); frontend/app/globals.css
    (auth-container, auth-card, form-group, btn-primary, alert-error, auth-links, nav-links); frontend/app/page.tsx
    (links /login e /register); frontend/tests/auth-pages.test.tsx (2 testes renderToString); frontend/vitest.config.mjs
    (oxc: false, esbuild jsx: "automatic" para compatibilidade com Next.js tsconfig "preserve").
  - Verificação: 13/13 Vitest passando; build inclui /login (2.37 kB) e /register (2.47 kB); lint e typecheck limpos;
    HTTP 200 confirmado nos dois routes em container running; 6 containers saudáveis.
  - Lição: vitest.config.mjs (não .ts) com oxc: false e esbuild jsx: "automatic" é necessário para transpile JSX com
    Next.js tsconfig que usa "preserve". Ficheiros copiados via docker compose cp precisam de chown -R node:node.

## Completed — 2026-09-16, Task 25 (Criar dashboard e upload com polling)
- [2026-09-16] Task: Task 25 verificada.
  - Alterações: frontend/lib/tenders.ts (tenderApi.list/upload/getStatus; generateIdempotencyKey; pollProcessingStatus
    com intervalMs, maxAttempts e onUpdate); frontend/app/dashboard/page.tsx ("use client", lista paginada, upload
    multipart com Idempotency-Key, polling com aria-live, estados loading/polling/done/error, links busca/chat somente
    PROCESSED, paginação, logout); frontend/app/globals.css (estilos dashboard, upload, tender-item, pagination, btn-secondary);
    frontend/tests/dashboard.test.ts (10 testes: list, list-error, upload com Idempotency-Key, FormData sem Content-Type,
    getStatus, generateIdempotencyKey único, pollProcessingStatus PROCESSED, FAILED e timeout).
  - Verificação: 23/23 Vitest passando; lint e typecheck limpos; build inclui /dashboard (3.93 kB); 6/6 containers saudáveis.
  - Lição: upload multipart — não definir Content-Type manualmente para preservar boundary do FormData; usar crypto.randomUUID()
    com fallback Math.random para idempotency key em ambientes sem crypto. mock.calls precisa de cast "as unknown as Array<[string, RequestInit]>" para TypeScript aceitar acesso ao segundo elemento do tuple.
  - Checkpoint Auth and upload UI (Tasks 23–25): ✅ verificado.

## Completed — 2026-09-16, Task 26 (Criar busca semântica)
- [2026-09-16] Task: Task 26 verificada.
  - Alterações: frontend/lib/search.ts (searchApi.search com POST /api/search/semantic/ omitindo campos opcionais ausentes),
    frontend/app/search/page.tsx (formulário acessível com label sr-only e filtro por edital, estados idle/loading/done/error/vazio,
    resultados com página/score/snippet, paginação prev/next, link para chat), frontend/app/globals.css (estilos da página de busca),
    frontend/tests/search.test.ts (6 testes: payload completo, omissão de opcionais, vazio, erro 400 e 429).
  - Verificação: 34/34 Vitest; lint e typecheck limpos; build com rota ○ /search 3.69 kB; HTTP 200 em /search no container.

## Completed — 2026-09-16, Task 27 (Criar chat com citações)
- [2026-09-16] Task: Task 27 verificada.
  - Alterações: frontend/lib/chat.ts (chatApi.send POST /api/tenders/{id}/chat/ com conversationId opcional),
    frontend/app/chat/page.tsx (useSearchParams em ChatPageContent envolvida em Suspense para CSR bailout; mensagens
    user/assistant em role="log"; painel de fontes com página/score/quote; tratamento de 409, 429 e remoção de mensagem
    órfã em erro; Enter para enviar), frontend/app/globals.css (estilos do chat e painel de citações),
    frontend/tests/chat.test.ts (5 testes: payload, conversationId, 409, 429 e ausência de evidência).
  - Verificação: 34/34 Vitest; lint e typecheck limpos; build com rota ○ /chat 3.39 kB; HTTP 200 em /chat no container.

## Lessons — 2026-09-16, verificação Fase 5
- [2026-09-16] Descoberta: arquivos copiados ao container via docker compose cp ficam root-owned e quebram
  typecheck (TS5033 EACCES escrevendo tsconfig.tsbuildinfo). É preciso chown node:node (frontend) ou 10001:10001 (api).
- [2026-09-16] Descoberta: useSearchParams em página estática exige componente separado envolvido em <Suspense>
  no Next 15 (missing-suspense-with-csr-bailout); sem isso o build falha ao pré-renderizar /chat.
- [2026-09-16] Decisão: GEMINI_API_KEY presente no .env fazia testes de busca/chat chamarem o Gemini real
  (score 0.0, não determinístico). Criado backend/tests/conftest.py com fixture autouse de sessão forçando
  GEMINI_API_KEY=mock para manter providers mockados e determinismo na suíte, conforme AGENTS.md.
  - Impacto: 114/114 pytest novamente; nenhum teste chamando rede.

## Completed — 2026-09-17, Task 28 (Criar teste E2E da demo) e Checkpoint Demo
- [2026-09-17] Task: Task 28 e Checkpoint Search and chat UI/Demo verificados.
  - Alterações: package.json raiz (devDep @playwright/test, scripts test:e2e), playwright.config.ts
    (testDir e2e, baseURL http://localhost:3000, timeout 240s, chromium), e2e/govintel-flow.spec.ts
    (fluxo cadastro → upload de PDF → processamento PROCESSED → busca semântica com snippet → chat com
    citações página/trecho), e2e/fixtures/edital-demo.pdf (PDF textual gerado via helper dos testes),
    docker-compose.e2e.yml (override GEMINI_API_KEY=mock para E2E determinístico),
    backend/apps/tenders/views.py (race de outbox corrigida: process_outbox_batch movido para
    transaction.on_commit no caminho com idempotência),
    backend/config/settings.py + backend/pyproject.toml/uv.lock (django-cors-headers 4.9.0, CORS restrito).
  - Verificação: `npx playwright test e2e/govintel-flow.spec.ts` passou 5 execuções consecutivas
    (com provider real e com mock via docker-compose.e2e.yml); 114/114 pytest; 34/34 vitest;
    lint/typecheck/build limpos (rotas /search, /chat, /dashboard); 6/6 containers saudáveis.

## Lessons — 2026-09-17, E2E e correções de Fase 5
- [2026-09-17] Descoberta: CORS não estava configurado; o frontend em localhost:3000 chamando a API em
  localhost:8000 (origem cruzada) era bloqueado pelo navegador. A threat model exige CORS restrito à origem
  configurada com credenciais. Adicionado django-cors-headers com CORS_ALLOWED_ORIGINS=[FRONTEND_ORIGIN],
  allow_credentials e allowlist de headers (authorization, x-csrftoken, idempotency-key) e métodos.
- [2026-09-17] Descoberta (bug real): process_outbox_batch() era chamado dentro de transaction.atomic() no
  caminho de upload com Idempotency-Key. O worker podia consumir a mensagem antes do commit do edital,
  terminar com TENDER_NOT_FOUND e o edital ficava PENDING indefinidamente (outbox SENT não é re-publicado).
  Correção: transaction.on_commit(process_outbox_batch). O caminho sem idempotência já publicava após o bloco.
- [2026-09-17] Descoberta: worker container não registrava a task pipeline.process_tender.v1 porque a imagem
  estava desatualizada (apps/pipeline só tinha __init__.py). Rebuild da imagem do worker resolveu; task
  versionada precisa estar na imagem, não só no api.
- [2026-09-17] Descoberta: página do chat usa useSearchParams; em Next 15 exige componente separado dentro de
  <Suspense> (missing-suspense-with-csr-bailout), senão o build falha na pré-renderização estática de /chat.
- [2026-09-17] Lição: E2E deve navegar via links (client-side) para preservar o access token em memória;
  page.goto() para /search e /chat perde o token e retorna 401 "Credenciais inválidas".
- [2026-09-17] Lição: npm test no frontend usa vitest; o e2e usa @playwright/test instalado na raiz
  (package.json raiz), com browsers chromium instalados no host via `npx playwright install chromium`.
  Execução: `npx playwright test e2e/govintel-flow.spec.ts`. Para E2E determinístico:
  `docker compose -f docker-compose.yml -f docker-compose.e2e.yml up -d --build`.

## Completed — 2026-09-17, Tasks 29–32 (Delivery local)

- [2026-09-17] Task 29 concluída: README e `docs/demo-script.md` agora descrevem
  setup desde `.env.example`, migrations, fila/exchange/DLQ, outbox pós-commit,
  storage privado, fixture PDF, provider mockado, comandos de teste e limpeza
  dos volumes. O README indica corretamente que Tasks 1–28 entregam o MVP.
- [2026-09-17] Task 30 concluída: `.github/workflows/ci.yml` executa em PR e
  push para `main` os gates de Ruff, testes backend com cobertura, ESLint/Prettier,
  typecheck, Vitest com cobertura, integração com serviços reais e health checks,
  auditoria, build das imagens e E2E Playwright com `GEMINI_API_KEY=mock`.
  Falhas encerram os jobs; branch protection required checks aguarda remoto GitHub.
- [2026-09-17] Task 31 concluída: adicionados `pytest-cov`, `pip-audit` e
  `@vitest/coverage-v8`; `uv.lock` e `frontend/package-lock.json` foram
  regenerados. `pip-audit --strict` inicialmente encontrou advisories em DRF
  3.16.1, LangChain 0.3.30 e pypdf 5.9.0; atualizações para DRF 3.18.1,
  LangChain 1.4.1 e pypdf 6.19.0 eliminaram os findings. npm audit permaneceu
  em zero; nenhuma remediation forçada ou vulnerabilidade ignorada.
- [2026-09-17] Task 32 concluída como preparação: Render foi escolhido e
  registrado em `docs/deployment.md` e `docs/decisions/ADR-001-render-demo.md`,
  com secrets por ambiente, health check `/health/`, smoke test e rollback para
  deploy anterior. `backend/Dockerfile` passou a aceitar `PORT` para serviços
  gerenciados. Limitação: `private_uploads` compartilhado localmente entre API e
  worker exige storage S3-compatible antes de uma publicação real; nenhum deploy
  ou push foi feito.

## Lessons — 2026-09-17, CI e dependências

- [2026-09-17] `pip-audit` pode reportar pacotes removidos ainda presentes no
  ambiente virtual; executar `uv sync --locked` antes da auditoria garante que o
  conjunto auditado corresponda ao lockfile.
- [2026-09-17] Next.js detectava o lockfile raiz durante o build do frontend e
  emitia warning; `outputFileTracingRoot: process.cwd()` em `frontend/next.config.ts`
  remove a ambiguidade mantendo os dois lockfiles necessários (E2E e frontend).
- [2026-09-17] A auditoria deve falhar por padrão. A descoberta de advisories
  levou a upgrades de dependências e testes completos, sem `--ignore-vuln` ou
  `audit fix --force`.
- [2026-09-17] Artefatos `coverage/` gerados no host entravam no contexto da
  imagem frontend e podiam ficar root-owned para o usuário `node`, quebrando o
  gate de cobertura no container. Adicionar `coverage` ao
  `frontend/.dockerignore` mantém o build limpo; o gate passou dentro do serviço.
- [2026-09-17] O typecheck do host também gera `tsconfig.tsbuildinfo`; sem
  exclusão no contexto, o arquivo impedia `tsc --noEmit` do usuário `node`.
  `frontend/.dockerignore` agora exclui `*.tsbuildinfo`; lint, typecheck e
  cobertura no container passaram sem warnings de artefatos locais.

## Lessons — 2026-09-16, falha de cadastro por origem local

- [2026-09-16] Reprodução no Playwright mostrou que `http://127.0.0.1:3000`
  era bloqueado pelo CORS, enquanto `http://localhost:3000` funcionava. O
  frontend usa a API em `http://localhost:8000`, então o preflight falhava
  antes do POST de cadastro e o usuário via apenas o erro genérico.
- [2026-09-16] Corrigido com `FRONTEND_ORIGINS`, lista explícita compartilhada
  por CORS e CSRF; ambiente local configurado para os dois aliases. O teste de
  preflight evita regressão sem liberar wildcard ou credenciais para origens
  não autorizadas.
- [2026-09-16] Validação: cadastro e login via loopback passaram; 115 testes
  backend, Ruff, Django check e `docker compose config --quiet` passaram; os
  seis serviços ficaram saudáveis.

## Lessons — 2026-09-16, cota do provider de embeddings

- [2026-09-16] O erro `429 embed_content_free_tier_requests` veio da cota do
  projeto Gemini configurado na `.env`; retries não criam quota e o problema
  não estava no parser de PDF nem na fila Celery.
- [2026-09-16] Para a demonstração local, ativado `GEMINI_API_KEY=mock`, que já
  é o caminho documentado para embeddings determinísticos sem chamadas externas.
  API e worker foram recriados mantendo os volumes.
- [2026-09-16] O edital que tinha falhado com 429 foi reencaminhado uma vez e
  concluiu `PROCESSED` com 224 chunks. Para produção, restaurar uma chave de
  projeto com cota/billing e manter o provider Gemini explícito.

## Completed — 2026-09-17, timeout do chat

- [2026-09-17] Task: chat retornava "The operation timed out." (abort do
  frontend após 15s) porque o endpoint de chat é síncrono (embeddings + LLM) e
  o MiMo via OpenRouter demora ~8s até para prompt trivial.
  - Alterações: frontend/lib/http.ts (timeoutMs opcional + default por env
    NEXT_PUBLIC_API_TIMEOUT_MS=15000), frontend/lib/chat.ts (timeoutMs: 60000
    no chat, alinhado ao gunicorn --timeout 60), frontend/components/chat-view.tsx
    (isTimeoutError trata DOMException TimeoutError de forma robusta e exibe
    mensagem amigável), backend adapters (OpenAI/ChatOpenAI com timeout=30 e
    max_retries=1 para falhar rápido em vez de travar).
  - Verificação: 42/42 Vitest (2 novos), ESLint/Prettier, tsc, build, 141/141
    pytest, E2E 1/1 (51.5s com provider real).
- [2026-09-17] Lição: `docker compose cp` grava só na camada do container; um
  `docker compose up -d --build` recria o container e apaga arquivos copiados.
  Quando containers divergem do host, reconstruir as imagens é o caminho seguro
  (fonte de verdade é o host).

## Completed — 2026-09-17, respostas sem frases cortadas

- [2026-09-17] Task: respostas do chat chegavam truncadas no meio da frase
  (ex.: "...término de acordo | com a"). Causas: chunker cortava em posições
  fixas de caracteres e o mock truncava o quote em 600 chars de forma dura.
  Detetive adicional: o prefixo "Com base no edital:" indica respostas do MOCK
  — se aparecer no chat com chave real configurada, o provider real falhou e
  caiu no fallback (agora registrado como WARNING no log da api).
  - Alterações: backend/apps/pipeline/chunker.py (_snap_end_to_sentence corta
    no fim da última frase completa da janela; corte duro só para frases
    maiores que o chunk; overlap baseado no fim real do chunk),
    backend/apps/conversations/rag_service.py (_assemble_complete_quote nunca
    corta no meio de frase; WARNING no fallback de ambos os providers reais),
    backend/tests/unit/pipeline/test_chunker.py (novo, 3 testes),
    backend/tests/integration/test_rag_chat.py (2 testes novos).
  - Verificação: 141/141 pytest, Ruff, Django check, E2E 1/1, api/worker
    reiniciados e saudáveis.

## Completed — 2026-09-17, Migração para MiMo-V2.5 via OpenRouter

- [2026-09-17] Task: chat e embeddings migrados para OpenRouter (escolha do
  usuário: OpenRouter + trocar embeddings também).
  - Chat: OpenRouterRAGService em backend/apps/conversations/rag_service.py
    usando langchain-openai 1.6.2 (ChatOpenAI, base_url OpenRouter, modelo
    xiaomi/mimo-v2.5, response_format json_object); prompt RAG extraído para
    constante compartilhada RAG_SYSTEM_INSTRUCTION (preserva a reescrita do
    usuário + exigência de resposta completa); parse tolerante de cercas
    Markdown (_parse_json_answer).
  - Embeddings: OpenRouterEmbeddingAdapter em backend/apps/intelligence/
    embeddings.py usando SDK openai 3.14.1 contra /embeddings, modelo
    openai/text-embedding-3-small com dimensions=768 (matryoshka — evita
    migração de schema) e input_type search_document/search_query; factory
    respeita EMBEDDING_PROVIDER (openrouter|gemini|mock), com OpenRouter
    preferido por padrão quando OPENROUTER_API_KEY válida existe.
  - Infra: settings (OPENROUTER_*), index_version do cache bumped v2→v3,
    conftest força OPENROUTER_API_KEY=mock e EMBEDDING_PROVIDER=mock,
    docker-compose.e2e.yml idem, ci.yml idem, .env.example documentado,
    pyproject/uv.lock (langchain-openai 1.6.2, openai 3.14.1).
  - Verificação: 136/136 pytest, Ruff, Django check, makemigrations --check,
    E2E Playwright 1/1 (mock) após rebuild --wait.
  - Pendência do usuário: definir OPENROUTER_API_KEY e
    EMBEDDING_PROVIDER=openrouter no .env e REENVIAR os editais (vetores
    antigos são do Gemini e incompatíveis com o novo espaço semântico).
- [2026-09-17] Lição: importar OpenAI/ChatOpenAI no topo do módulo, não dentro
  de __init__/métodos — patch de testes (monkeypatch de atributo do módulo)
  exige o símbolo no namespace do módulo.

## Completed — 2026-09-17, leitura de tabelas e exclusão de editais

- [2026-09-17] Task: melhorar leitura de tabelas nos editais e expor exclusão
  de editais no dashboard.
  - Tabelas: pypdf 6 não tem extract_tables; extração migrada para modo layout
    (preserva colunas espacialmente) em backend/apps/pipeline/pdf_extractor.py,
    com _compact_layout_columns convertendo sequências de 2+ espaços em " | "
    (ex.: "Item | Quantidade | Valor") e fallback para o modo normal em falhas
    (ex.: PDF sem /Tf). Fixture create_table_pdf em tests/fixtures/pdf_helpers.py.
  - Exclusão: frontend/lib/tenders.ts (tenderApi.remove DELETE /api/tenders/{id}/),
    frontend/app/dashboard/page.tsx (botão Excluir por edital com
    window.confirm, remoção otimista, recarga da lista, estado deletingId,
    alert de erro), frontend/app/globals.css (.btn-danger).
  - Importante: o usuário reescreveu o system_instruction do RAG (anti-injeção,
    citações literais); a versão final preserva o texto do usuário e adiciona
    apenas a exigência de resposta COMPLETA com todos os trechos relevantes.
  - Verificação: 128/128 pytest, Ruff, Django check, makemigrations --check,
    40/40 Vitest, ESLint/Prettier, build Next, E2E Playwright 1/1; api
    reiniciada e frontend rebuilt --wait.
- [2026-09-17] Lição: pypdf 6 não expõe extração de tabelas; o modo layout
  (extraction_mode="layout") é o caminho nativo para preservar colunas, mas
  exige fonte registrada no PDF — sem /Tf ele lança PdfReadError, daí o
  fallback obrigatório para o modo normal.

## Completed — 2026-09-17, respostas completas no chat RAG

- [2026-09-17] Task: respostas do chat com Gemini real estavam incompletas.
  - Causas: retrieval com top_k=5 (muito estreito para perguntas que cruzam
    seções) e prompt pedindo resposta "clara e objetiva", que induz brevidade.
  - Alterações: backend/apps/conversations/rag_service.py (constante
    CHAT_RETRIEVAL_TOP_K=8 alinhada ao default da SPEC; prompt exige resposta
    COMPLETA, considerando TODOS os trechos relevantes e listando itens,
    prazos, valores e condições sem omitir nem inventar),
    backend/tests/integration/test_rag_chat.py (testes do prompt completo e do
    top_k via FakeClient/monkeypatch de google.genai.Client).
  - Verificação: 126/126 pytest, Ruff limpo, Django check limpo; api reiniciada
    e saudável.
- [2026-09-17] Lição: Add-Content do PowerShell 5.1 grava em encoding ANSI e
  corrompe acentos em arquivos UTF-8; usar as ferramentas de escrita com
  suporte a UTF-8 (Write/Edit) ou Add-Content -Encoding UTF8.
- [2026-09-17] Lição: gunicorn sem --reload mantém módulos em memória; após
  docker compose cp, é preciso `docker compose restart api` para o novo
  código Python valer.

## Completed — 2026-09-17, OCR de PDFs escaneados e citações sem `text`

- [2026-09-17] Task: limitação funcional de OCR resolvida e legado `text` removido.
  - Alterações: backend/apps/pipeline/ocr.py (novo, rasteriza com pypdfium2 e
    reconhece com pytesseract/Tesseract `por`, `ocr_available` cacheado),
    backend/apps/pipeline/pdf_extractor.py (ocr_fn injetável, OCR por página sem
    texto com fallback gracioso), backend/apps/conversations/rag_service.py
    (citations apenas com `quote`), backend/Dockerfile (tesseract-ocr +
    tesseract-ocr-por), .github/workflows/ci.yml (instalação de Tesseract nos
    jobs backend), .env.example (OCR_ENABLED/OCR_LANGUAGE), backend/pyproject.toml
    e uv.lock (pypdfium2 5.13.0, pytesseract 0.3.13, pillow 11.3.0),
    tests/fixtures/pdf_helpers.py (create_scanned_pdf e
    create_mixed_text_and_scanned_pdf), tests/unit/pipeline/test_ocr.py (6 testes).
  - Verificação: 124/124 pytest, Ruff limpo, Django check e makemigrations
    --check limpos, 34/34 Vitest, lint/typecheck frontend limpos, E2E Playwright
    1/1 após rebuild --wait. Nenhum deploy ou push realizado.

## Completed — 2026-09-17, toggle de citações no chat

- [2026-09-17] Task: corrigido "clique para ver" das citações no chat, que não
  produzia efeito visível (o painel lateral já mostrava as citações da última
  resposta; em telas estreitas o painel fica fora da vista).
  - Alterações: frontend/components/chat-view.tsx (novo; ChatView movida de
    app/chat/page.tsx porque o Next não permite exports nomeados em page),
    frontend/app/chat/page.tsx (wrapper fino com Suspense),
    frontend/app/globals.css (.chat-citations-toggle e .chat-citations-inline),
    frontend/tests/chat-citations.test.tsx (novo; jsdom + @testing-library/react
    já presentes, jsdom 27 adicionado como devDep, scrollIntoView stubado),
    frontend/package.json e package-lock.json.
  - Comportamento novo: botão acessível "N citação(ões) — ver/ocultar fontes"
    com aria-expanded expande as citações inline sob a própria mensagem e mantém
    o painel lateral sincronizado.
  - Verificação: 35/35 Vitest, tsc --noEmit limpo, ESLint/Prettier limpos,
    build de produção ok, E2E Playwright 1/1 após rebuild --wait.

## Lessons — 2026-09-17, OCR

- [2026-09-17] `docker compose exec` roda como usuário non-root; chown de
  arquivos copiados exige `docker compose exec --user root api chown ...`.
- [2026-09-17] OCR falho ou ausente degrada para página vazia em vez de
  interromper o pipeline; só quando nenhuma página produz texto o edital
  termina `FAILED` com `NO_TEXT_EXTRACTED`, preservando PDFs mistos
  (parte textual, parte escaneada).
- [2026-09-17] Citação sem `text` não quebrou consumidores: o frontend e o
  contrato público já usavam apenas `quote`; mensagens antigas persistidas com
  `text` permanecem inofensivas no JSONField.

## Lessons — 2026-09-17, qualidade de busca e chat

- [2026-09-17] O mock de embedding era determinístico, mas pseudoaleatório;
  isso fazia a busca local escolher chunks sem relação com a pergunta. A busca
  agora amplia candidatos e faz reranking lexical normalizado em português,
  preservando o vetor para o provider real.
- [2026-09-17] O snippet começava sempre no início do chunk, ocultando o trecho
  que justificava o resultado. Ele agora é centrado no primeiro termo encontrado.
- [2026-09-17] `MockRAGService` retornava o chunk inteiro e aceitava uma
  similaridade fraca como evidência. A resposta agora seleciona frases pertinentes,
  limita o tamanho e recusa correspondência vetorial fraca.
- [2026-09-17] O backend serializava citações em `text`, mas a tela consumia
  `quote`. `quote` passou a ser canônico e `text` foi mantido temporariamente
  para compatibilidade com consumidores existentes.
- [2026-09-17] A SPEC já exigia instruções em `contents` e proibia `task_type`
  para Gemini Embedding 2. O adapter real foi alinhado e os vetores existentes
  continuam válidos para o modo mock graças ao reranking lexical.
- [2026-09-17] Verificação: 118 testes backend, Ruff, Django check, Compose
  config, E2E Playwright 1/1 e 34 testes frontend passaram. Nenhum chunk atual
  dos três editais maiores está vazio ou sem embedding.
- [2026-09-17] Revisão de segurança/CI adversarial: `APIView` deixa registro,
  login, refresh e logout `csrf_exempt`; sem uma verificação explícita, até
  Origin externo sem token CSRF retorna 204. `NUM_PROXIES=None` faz o DRF
  aceitar `X-Forwarded-For` no identificador de login. Registro, upload e
  refresh não têm throttling e o throttling falha aberto quando Redis falha.
- [2026-09-17] Revisão de refresh: a rotação blacklista apenas o token usado;
  não há família de tokens nem revogação da substituição quando ocorre reuse,
  e não existe lock/transação cobrindo concorrência.
- [2026-09-17] Revisão de RAG/pipeline: `validate_citations` substitui quote
  inválido por texto arbitrário e conserva a resposta mesmo sem citações;
  `process_tender_v1` não grava o modelo/provider nos metadados do chunk e a
  busca não filtra fingerprint. Fallback para mock mascara falhas do provider.
- [2026-09-17] Revisão de storage/erros: `_resolve_path('../../etc/passwd')`
  resolve fora de `UPLOAD_ROOT`; erros de parser/provider são persistidos e
  expostos por `errorMessage`.
- [2026-09-17] Revisão de CI/dependências: `backend-quality` roda a suíte
  inteira sem serviços para o host `db`; `pip-audit --strict` atual falha em
  Pillow 11.3.0 com 35 advisories (fixes na série 12.x), embora npm audit
  da raiz e frontend passe. O relay do outbox/reconciliador não tem caller
  periódico. Nenhum código foi alterado; correções de auth/throttling exigem
  aprovação explícita antes de implementação.

## Lessons — 2026-09-17, estabilização real antes do chat

- [2026-09-17] Provider de embedding precisa ser parte do estado do chunk.
  Chunks antigos estavam marcados como Gemini enquanto o runtime consultava
  OpenRouter; provider, modelo, versão, dimensão, normalização e fingerprint
  agora são persistidos e o retrieval impede mistura de provider.
- [2026-09-17] A reindexação foi executada somente depois de um dry-run: 29
  editais processados foram reindexados com OpenRouter, totalizando 55 chunks
  atuais homogêneos. O comando `reindex_embeddings` falha se algum edital não
  concluir, evitando declarar uma validação parcial como concluída.
- [2026-09-17] Fail-closed de citações pode devolver insuficiência mesmo com
  retrieval válido quando o LLM paraphraseia quotes. Uma única tentativa
  corretiva melhora a taxa de grounding sem aceitar quote divergente; a suíte
  inclui teste para a primeira tentativa inválida e a segunda literal.
- [2026-09-17] Pillow 12.3.0 removeu os advisories encontrados pelo
  `pip-audit --strict`; o lockfile continua usado na imagem Docker.
- [2026-09-17] Verificação final: 151 testes backend, 42 frontend, Ruff,
  typecheck/lint, Django check, migrations check, pip-audit, Compose config e
  worker ping passaram. Chat real após reindexação retornou 6 citações
  verificadas; nenhum segredo ou conteúdo documental foi impresso.

## Decisão — redesign frontend (2026-09-17)

- [2026-09-17] A interface usa papel editorial (`#F4F0E8`), tinta (`#17212B`),
  teal institucional (`#177E89`), dourado de sinal (`#D6A84F`) e linhas
  quentes (`#D8D2C8`). Source Serif 4/Georgia comunica leitura; IBM Plex
  Sans/Avenir/Segoe UI cobre controles sem depender de fonte remota.
- [2026-09-17] O elemento recorrente é uma linha de evidência: aparece em
  editais e resultados e culmina no rail de citações do chat. Isso mantém a
  identidade ligada ao trabalho do produto, sem grades ou gradientes de SaaS.
- [2026-09-17] A revisão visual real foi feita após rebuild do container em
  `/`, `/login`, `/dashboard`, `/search` e `/chat?tenderId=demo`, em viewport
  1280x720. Os fluxos mantiveram os IDs usados por testes e a suíte permaneceu
  verde (43 Vitest).
- [2026-09-17] O wordmark foi extraído para `frontend/components/product-brand.tsx`;
  a mesma marca agora serve home, login e cadastro. A suíte passou com um
  worker; o timeout observado em execução paralela é contenção do ambiente e
  foi reproduzido como sucesso no teste isolado.
- [2026-09-17] Smoke test Playwright percorreu as cinco rotas em viewport
  1280x720 e salvou PNGs em `docs/frontend/evidence/`. Não houve page error ou
  erro JavaScript; as rotas protegidas emitiram somente o 401 esperado ao
  carregar dados sem sessão.

## Lessons — 2026-09-17, CSRF entre localhost e 127.0.0.1

- [2026-09-17] CORS permitir duas origens não torna cookies `SameSite=Lax`
  compartilháveis entre `localhost` e `127.0.0.1`; o navegador trata os hosts
  como sites diferentes e o Django responde 403 quando o cookie CSRF não chega.
- [2026-09-17] A correção deve manter o frontend e a API no mesmo hostname
  durante a demo. O cliente agora remapeia somente hosts locais; não altera URL
  externa configurada para produção.
- [2026-09-17] Playwright validou cadastro e login nos dois hosts locais sem
  side effect de conta, usando payloads inválidos que chegam ao serializer com
  400/401 em vez de falharem na camada CSRF.

## Completed — 2026-09-18, OpenCode e embeddings locais

- [2026-09-18] A configuração foi separada entre LLM e embeddings. O padrão é
  OpenCode Zen (`mimo-v2.5`) para chat e `intfloat/multilingual-e5-base` local
  em CPU para vetores 768D; chaves de providers legados não alteram a seleção.
- [2026-09-18] O adapter E5 usa `passage:`/`query:`, `normalize_embeddings=True`,
  batch configurável, cache Hugging Face compartilhado e fingerprint de
  modelo/revisão/preprocessamento. O lock foi atualizado para torch CPU, sem
  pacotes CUDA/triton.
- [2026-09-18] O retrieval passou a exigir provider, modelo, versão, dimensão,
  normalização e fingerprint iguais ao adapter ativo. O chat OpenCode exige
  documentId/chunkId/pageNumber/quote literais e uma única correção no máximo.
- [2026-09-18] `reindex_embeddings` foi refeito para staging corpus-wide,
  promoção transacional e rollback explícito de gerações antigas. Testes focados
  de provider/embeddings/RAG passaram (27). Reindex da base real ainda não foi
  marcado como concluído antes do rebuild e dry-run.

## Verified — 2026-09-18, gate final da migração

- [2026-09-18] Docker API/worker foi reconstruído com o lock CPU-only. Check,
  migrations check, Ruff e a suíte backend completa passaram: 167 testes.
  Frontend lint/typecheck/build e 43 testes passaram.
- [2026-09-18] Dry-run contra a base local encontrou 29 editais processados e
  55 chunks current. Reindexação real local terminou em 88,88 s com 55 chunks
  novos, todos `local/intfloat/multilingual-e5-base/main/768/L2` e fingerprint
  único. As gerações anteriores permaneceram no banco como não-current.
- [2026-09-18] O Compose passou configuração e serviços API/worker ficaram
  saudáveis. Não houve push, deploy ou remoção de volumes.
- [2026-09-18] `pip-audit` não consegue resolver o wheel `torch+cpu` fora do
  índice PyTorch; o CI agora exporta o lock excluindo apenas esse pacote,
  executa `pip-audit --strict --disable-pip` nos demais pacotes e valida em
  separado que o torch instalado termina em `+cpu`. O resultado foi zero
  vulnerabilidades conhecidas.

## Verified — 2026-09-18, modelo de chat DeepSeek V4 Flash

- [2026-09-18] O padrão OpenCode foi atualizado de `mimo-v2.5` para
  `deepseek-v4-flash` em settings, Compose, exemplo de ambiente e testes. O
  modelo consta no catálogo Zen e usa o endpoint compatível com Chat
  Completions; a validação exata e o fail-closed permanecem ativos.
- [2026-09-18] Após reconstrução da API/worker, o teste focado passou (10), a
  suíte backend passou (167), Ruff passou e `manage.py check` não encontrou
  problemas. Nenhuma reindexação foi necessária: embeddings e espaço vetorial
  não mudaram.

## Verified — 2026-09-18, README técnico expandido

- [2026-09-18] O `README.md` foi reestruturado como porta de entrada técnica do
  projeto. Agora explica objetivo, stack, arquitetura, multi-tenancy, upload
  idempotente, outbox/Celery, OCR, embeddings, pgvector, reindexação, retrieval,
  RAG, grounding, citações, sessão, segurança, providers, execução, testes,
  CI, deploy, limites e conceitos abordados.
- [2026-09-18] A documentação normativa continua distribuída em `docs/` e o
  README aponta para contratos, threat model, arquitetura, demo, deploy,
  plano e checklist. Prettier validou o arquivo; nenhum comportamento de
  aplicação foi alterado.
