# Contexto operacional

## OCR e citações sem `text` — 2026-09-17

- Implementado a pedido do usuário: PDFs escaneados agora passam por OCR local.
  Páginas sem camada de texto são rasterizadas com pypdfium2 (300 dpi) e
  reconhecidas com Tesseract (pacote `por`); `OCR_ENABLED`/`OCR_LANGUAGE`
  controlam o comportamento e, sem toolchain ou desativado, o fluxo mantém
  `NO_TEXT_EXTRACTED`. Injeção de `ocr_fn` em `extract_pdf_pages` mantém o
  serviço puro e testável.
- Campo legado `text` removido das citações: `validate_citations` emite apenas
  `quote` (frontend já consumia só `quote`); mapeamento da resposta do LLM
  atualizado; nenhum consumidor restante no frontend ou nos testes.
- Ambiente: Tesseract 5.3.0 + `tesseract-ocr-por` instalados no Dockerfile
  (api/worker) e nos jobs backend do CI; pypdfium2 5.13.0, pytesseract 0.3.13
  e pillow 11.3.0 travados em uv.lock.
- Evidência: 124 pytest (6 novos de OCR, incluindo recuperação real de página
  escaneada), Ruff, Django check, makemigrations --check, 34 Vitest,
  lint/typecheck frontend e E2E Playwright 1/1 após rebuild com `--wait`.
- Próximo gate: testar um PDF escaneado real na interface; revisão humana e
  storage S3-compatible continuam pendentes para produção.

## Toggle de citações no chat — 2026-09-17

- Corrigido: "clique para ver" não fazia nada visível porque o painel lateral
  já exibia as citações da última resposta e, em telas estreitas, ficava fora
  da vista. Agora cada mensagem com citações tem um botão acessível
  ("ver/ocultar fontes", aria-expanded) que expande as citações inline e mantém
  o painel sincronizado.
- Estrutura: UI do chat movida para frontend/components/chat-view.tsx
  (exports nomeados não são permitidos em page.tsx do Next).
- Evidência: 35/35 Vitest (novo teste de interação com jsdom), typecheck,
  ESLint/Prettier, build e E2E Playwright 1/1 após rebuild.

## Respostas completas no chat RAG — 2026-09-17

- Causa das respostas incompletas com Gemini real: retrieval com top_k=5 e
  prompt que pedia resposta "clara e objetiva" (induzia brevidade).
- Correção: CHAT_RETRIEVAL_TOP_K=8 (default da SPEC) e prompt exigindo resposta
  COMPLETA com todos os trechos relevantes, listando itens/prazos/valores sem
  omitir ou inventar. Grounding e allowlist de citações inalterados.
- Evidência: 126/126 pytest, Ruff e Django check limpos; api reiniciada.
- Próximo gate: repetir perguntas amplas no chat com a chave real e observar
  consumo de cota.

## Tabelas e exclusão de editais — 2026-09-17

- Tabelas: extração agora usa pypdf em modo layout com colunas compactadas em
  " | " (preserva linhas/colunas de tabelas para chunking/RAG) e fallback para
  o modo normal quando o layout falha. Editais JÁ processados não são
  reprocessados: é preciso excluir e reenviar o PDF para reindexar com tabelas.
- Exclusão: botão Excluir no dashboard com confirmação; remove edital, blob
  privado, chunks, conversas e invalida o cache do tenant (contrato 204 já
  existente no backend).
- Evidência: 128/128 pytest, 40/40 Vitest, Ruff, Django check, lint/typecheck,
  builds e E2E 1/1.
- Próximo gate: reenviar um edital com tabelas e validar busca/chat citando
  linhas da tabela.

## Migração OpenRouter (MiMo-V2.5) — 2026-09-17

- Chat: xiaomi/mimo-v2.5 via langchain-openai/ChatOpenAI (base_url
  openrouter.ai/api/v1, response_format JSON). Prompt preservado
  (RAG_SYSTEM_INSTRUCTION compartilhada com o caminho Gemini).
- Embeddings: openai/text-embedding-3-small com dimensions=768 via
  POST /embeddings da OpenRouter — sem migração de schema pgvector(768);
  input_type distingue documento de consulta; cache bumped para index v3.
- Pendências do usuário: colocar OPENROUTER_API_KEY no .env,
  EMBEDDING_PROVIDER=openrouter e REENVIAR todos os PDFs (espaço vetorial
  novo; vetores Gemini antigos não são compatíveis).
- Evidência: 136/136 pytest (8 novos), Ruff/check/migrations limpos, E2E 1/1.

## Frases sem corte — 2026-09-17

- Chunker agora corta no fim de frases completas (snap em [.!?] ou quebra de
  linha); overlap calculado a partir do corte real. Mock do RAG nunca trunc
  quote no meio de frase. Fallback de provider real→mock agora emite WARNING
  no log — se o chat responder "Com base no edital:", o provider real falhou
  ou não está configurado.
- Evidência: 141/141 pytest, Ruff, Django check, E2E 1/1, containers saudáveis.
- Pendência: usuário confirmar OPENROUTER_API_KEY no .env, recriar api/worker
  e reenviar os editais (novo chunking só vale para PDFs reprocessados).

## Investigação — 2026-09-17, qualidade de busca e chat

- Sintoma reproduzido: o provider local `GEMINI_API_KEY=mock` gerava vetores
  determinísticos pseudoaleatórios, sem relação semântica entre pergunta e
  trecho; o reranking vetorial podia escolher um chunk sem os termos da pergunta.
- Evidência de ingestão: os três editais processados maiores têm 224–295 chunks,
  nenhum chunk atual vazio ou sem embedding e texto médio de 638–745 caracteres.
  A extração textual não é a causa principal nesses documentos.
- Correção implementada: `VectorSearchRepository.search` aceita `query_text`,
  amplia candidatos e aplica reranking lexical normalizado para português; o
  snippet passa a ser centrado no termo encontrado. A rota de busca e o RAG
  enviam a pergunta textual, e o cache usa `indexVersion=v2` para não reutilizar
  resultados antigos.
- Correção implementada: `MockRAGService` seleciona as frases com maior
  sobreposição, limita a resposta ao trecho pertinente e declara insuficiência
  quando só há correspondência vetorial fraca. Citações retornam `quote` (com
  `text` mantido por compatibilidade), página e score; isso alinha o backend ao
  campo consumido pela tela.
- Correção implementada: `GeminiEmbeddingAdapter` segue o formato do
  `gemini-embedding-2` definido na SPEC, com instruções em `contents` e sem
  `task_type`; dimensões continuam fixadas em 768.
- Evidência: 118 testes backend, Ruff, Django check, Compose config, E2E
  Playwright 1/1 e 34 testes frontend passaram. Busca manual nos editais grandes
  retornou os primeiros chunks com termos da consulta e citações com `quote`.
- Próximo gate: repetir perguntas reais na interface. PDFs escaneados continuam
  sem OCR e devem ser marcados como limitação caso um arquivo sem camada de texto
  seja usado.

- Estado inicial (2026-09-16): somente specs/docs/tasks; sem Git, manifests,
  lockfiles, código ou arquivos de contexto anteriores.
- Capability: web-application. Tasks 29–32 CONCLUÍDAS localmente. Próximo gate:
  revisão humana e, quando houver remoto, configuração de required checks; nenhum deploy foi executado.
- Fontes obrigatórias lidas: CAPABILITY-MAP, SPEC e 8 specs de módulo;
  6 documentos em docs; tasks/plan e tasks/todo.
- Dependências: Docker Engine 29.6.1, Compose 5.2.0 disponíveis após iniciar
  Docker Desktop. Seis containers saudáveis (db, redis, rabbitmq, api, worker, frontend).
- Checkpoints concluídos: Infrastructure scaffold (1–3), Authentication contract (4–6), Foundation (7), Upload contract (8–10), Processing contract (11–13), Ingestion (8–13), Vector foundation (14–16), Retrieval and RAG contract (17–19), Intelligence (14–19), Protection (20–22), Auth and upload UI (23–25), Search and chat UI (26–28).
- Fase 5 CONCLUÍDA (Tasks 23–28). Fase 6 de Delivery concluída localmente
  (Tasks 29–32); Checkpoint Demo e gates operacionais verificados.
- Task 28 evidências: projeto Playwright na raiz (package.json com @playwright/test,
  playwright.config.ts baseURL localhost:3000, timeout 240s); `e2e/govintel-flow.spec.ts`
  (cadastro → upload → processamento → busca → chat com citações);
  `e2e/fixtures/edital-demo.pdf` textual; `docker-compose.e2e.yml` com GEMINI_API_KEY=mock
  para E2E determinístico; `npx playwright test e2e/govintel-flow.spec.ts` passou 5x
  consecutivas (real e mock). 114/114 pytest; 34/34 vitest; lint/typecheck/build limpos.
- Fase 6 evidências (2026-09-17): README e `docs/demo-script.md` consolidados;
  `.github/workflows/ci.yml` cobre Ruff, ESLint/Prettier, tsc, testes com
  cobertura, integração com pgvector/Redis/RabbitMQ saudáveis, builds, E2E
  mockado, auditorias e varredura de secrets; `.github/dependabot.yml` cobre
  os lockfiles raiz, frontend e backend. `pip-audit --strict` e ambos os
  `npm audit --audit-level=high` passaram após atualizar DRF para 3.18.1,
  LangChain para 1.4.1 e pypdf para 6.19.0; 114/114 pytest, 34/34 Vitest,
  cobertura backend 95% e frontend 76.6% passaram. Render foi escolhido como
  alvo de preparação em `docs/deployment.md`; storage compartilhado de PDF é
  limitação conhecida e exige adapter S3-compatible antes de produção.
- Verificação final (2026-09-17): imagens com bases fixadas por digest foram
  reconstruídas; `docker compose config --quiet` passou; seis serviços ficaram
  saudáveis e `celery inspect ping` retornou `pong`. O E2E mockado passou 1/1
  após os upgrades. `frontend/.dockerignore` agora exclui `coverage/` e
  `*.tsbuildinfo`, evitando warnings e erros EACCES nos gates non-root; lint,
  typecheck e cobertura no container passaram (34/34 testes, 76,6%).
- Correções descobertas pelo E2E (Fase 5): (1) CORS não estava configurado — adicionado
  `django-cors-headers` (CORS_ALLOWED_ORIGINS=FRONTEND_ORIGIN, credentials, headers/methods
  restritos) exigido pela threat model; (2) race em upload idempotente — `process_outbox_batch()`
  era chamado dentro de `transaction.atomic()`, então o worker podia consumir a mensagem antes
  do commit do edital (tender ficava PENDING para sempre); migrado para
  `transaction.on_commit(process_outbox_batch)` em backend/apps/tenders/views.py.
- Task 26 evidências: `frontend/lib/search.ts` (`searchApi.search` POST /api/search/semantic/,
  omitindo opcionais ausentes), `frontend/app/search/page.tsx` (formulário acessível, filtro por edital,
  estados idle/loading/done/error/vazio, resultados com página/score/snippet, paginação), estilos em
  globals.css; 6 testes em `tests/search.test.ts`; 34/34 vitest; lint/typecheck/build com rota `○ /search 3.69 kB`.
- Task 27 evidências: `frontend/lib/chat.ts` (`chatApi.send`), `frontend/app/chat/page.tsx` com `useSearchParams`
  em `ChatPageContent` envolvida em `<Suspense>` (CSR bailout), painel de citações, tratamento de 409/429 e
  remoção de mensagem órfã; 5 testes em `tests/chat.test.ts`; 34/34 vitest; lint/typecheck/build com rota
  `○ /chat 3.39 kB`; /search, /chat e /dashboard retornam 200 no container.
- Ajustes de verificação da Fase 5: arquivos copiados ao container via `docker compose cp` precisam de
  `chown node:node` (typecheck TS5033); `conftest.py` em backend/tests força `GEMINI_API_KEY=mock` para
  manter providers mockados e determinismo na suíte (AGENTS.md), evitando chamadas reais ao Gemini
  quando a chave está no `.env` (busca/chat retornavam score 0.0).
- Task 25 evidências: módulo `frontend/lib/tenders.ts` com `tenderApi.list/upload/getStatus`,
  `generateIdempotencyKey()` e `pollProcessingStatus()` (intervalMs, maxAttempts, onUpdate);
  `frontend/app/dashboard/page.tsx` (`"use client"`) com lista paginada, upload multipart com
  `Idempotency-Key`, polling em tempo real com `aria-live`, estados loading/polling/done/error,
  links busca/chat somente em PROCESSED, paginação, logout; 10 novos testes em `tests/dashboard.test.ts`;
  23/23 vitest; lint e typecheck limpos; build inclui `○ /dashboard 3.93 kB`; 6/6 containers saudáveis.
- Task 23 evidências: tipos canônicos de domínio e envelopes definidos em `frontend/lib/types.ts` (`ApiError`,
  `User`, `Company`, `AuthResponse`, `Tender`, `ProcessingStatus`, `SearchResultItem`, `Citation`, `Message`, etc.);
  gerenciador de autenticação em memória implementado em `frontend/lib/auth.ts` (`authStore`, `getAccessToken`,
  `setAccessToken`, `ensureCsrfToken`, `refreshAccessToken`, etc.) garantindo que access token nunca é exposto
  em `localStorage` ou `sessionStorage`; cliente HTTP em `frontend/lib/http.ts` (`apiRequest`, `ApiClientError`)
  com injeção automática de Bearer token, injeção de CSRF token em mutações, auto-refresh transparente em 401
  com deduplicação (single-flight) e retry imediato; 11/11 testes Vitest passando no frontend (8 novos testes em
  `tests/auth.test.ts` e 3 em `tests/http.test.ts`); build Next.js de produção passando sem erros; lint e typecheck
  100% limpos; 114/114 pytest passando no backend.
- Task 22 evidências: classes de throttling implementadas em `apps.core.throttling` (`BaseGovIntelThrottle`,
  `LoginThrottle`, `SearchThrottle`, `ChatThrottle`) com Redis; chaves canônicas `govintel:v1:throttle:{ident}:{endpoint}`
  (IP para login anônimo, userId para busca e chat autenticados); taxas configuradas em `REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]`
  (login 5/min, busca 30/min, chat 15/min); views `LoginView`, `SemanticSearchView` e `TenderChatView` integradas;
  excesso retorna 429 no envelope comum com `Retry-After`; limites provados independentes por usuário e endpoint;
  falhas de cache/infraestrutura mascaradas sem vazar dados confidenciais (hosts, senhas, stack traces);
  `custom_handler404` e `custom_handler500` registrados em `config.urls`; 114/114 pytest passando no backend (7 novos testes em
  `test_throttling.py`); ruff check ., django check e makemigrations --check 100% limpos; 3/3 vitest limpos.
- Task 21 evidências: invalidação de cache integrada na task Celery `pipeline.process_tender.v1` (incrementando
  `dataRevision` via `increment_company_data_revision` na promoção atômica para `PROCESSED`) e na rota de deleção
  `DELETE /api/tenders/{id}/`; preservação estrita do cache de outros tenants comprovada; 107/107 pytest passando no backend
  (3 testes em `test_cache_invalidation.py`); ruff check ., django check e makemigrations --check 100% limpos; 3/3 vitest limpos.
- Task 20 evidências: módulo de cache canônico `apps.intelligence.cache` gerando chaves versionadas
  `govintel:v1:semantic:{companyId}:{scope}:{dataRevision}:{embeddingVersion}:{indexVersion}:{sha256(canonicalQuery+filters)}`;
  integração no Redis em `SemanticSearchView`; TTL configurável por `SEARCH_CACHE_TTL` (default 300s);
  mecanismo de `dataRevision` por tenant permitindo invalidação imediata sem varredura SCAN;
  104/104 pytest passando no backend (5 novos testes de integração em `test_search_cache.py`);
  ruff check ., django check e makemigrations --check 100% limpos; 3/3 vitest limpos.
- Task 19 evidências: endpoint `POST /api/tenders/{id}/chat/` implementado com `TenderChatView` em `apps.conversations.views`
  e `ChatRequestSerializer`; rejeição com 409 CONFLICT para editais não processados (PENDING, PROCESSING, FAILED)
  e 404 para editais de outro tenant; pipeline RAG em `rag_service.py` com recuperação vetorial, delimitação de contexto
  como dado não confiável (`<context_document id="..." page="...">`), allowlist e validação estrita de citações contra
  os chunks recuperados (eliminando IDs alucinados e checando quotes persistidos); declaração de insuficiência com
  mensagem segura quando não há evidência; dependência `langchain 0.3.30` adicionada e travada em `uv.lock`; 99/99 pytest
  passando no backend (10 novos testes em `test_rag_chat.py`); ruff check ., django check e makemigrations --check 100% limpos; 3/3 vitest limpos.
- Task 18 evidências: modelos `Conversation` e `Message` implementados em `apps.conversations.models`;
  validação estrita rejeita editais com status diferente de `PROCESSED` e editais pertencentes a outro tenant;
  mensagens preservam ordem cronológica e role (`user`/`assistant`) com campo estruturado `citations`;
  serializers `MessagePublicSerializer` e `ConversationPublicSerializer` em camelCase; migration
  `0001_initial` de conversas aplicada no PostgreSQL real; 89/89 pytest passando no backend (6 novos
  testes de integração e serializers em `test_conversation_models.py`); ruff check ., django check e
  makemigrations --check 100% limpos; 3/3 vitest limpos.
- Task 17 evidências: endpoint `POST /api/search/semantic/` em `apps.intelligence.views.SemanticSearchView`,
  com `SemanticSearchRequestSerializer` validando query obrigatória, limites de topK (máx 50) e pageSize (máx 50),
  page >= 1 e pertença de tenderId ao tenant autenticado; `VectorSearchRepository` com overfetch iterativo,
  fallback exato forçado com `enable_indexscan = off` para cobrir tenants pequenos/enviesados/vazios,
  e campo `snippet` truncado em 200 caracteres; envelope paginado `{ data, pagination }`; 83/83 pytest passando
  no backend (8 novos testes em `test_semantic_search.py` e 2 novos em `test_vector_intelligence.py`);
  ruff check ., django check e makemigrations --check 100% limpos; 3/3 vitest limpos.
- Task 16 evidências: `MockEmbeddingAdapter` e `get_embedding_adapter` criados em `apps.intelligence.embeddings`
  gerando vetores determinísticos normalizados de 768 dimensões com interface compatível com `GeminiEmbeddingAdapter`;
  task Celery `pipeline.process_tender.v1` integrada com `get_embedding_adapter` para geração em batch e persistência
  de vetores em `DocumentChunk` da geração staged; falha no provider de embedding limpa geração staged e marca `FAILED`
  sem promover para `PROCESSED` e sem afetar geração corrente anterior; 73/73 pytest passando no backend (incluindo
  novos testes unitários e de integração); ruff check ., django check e makemigrations --check 100% limpos; 3/3 vitest limpos.
- Task 15 evidências: modelo DocumentChunk estendido com VectorField(768), metadados de embedding
  (embedding_model_name, embedding_model_version, embedding_dimensions, normalization, preprocessing_fingerprint),
  índice B-tree composto doc_chunk_comp_curr_idx (company, is_current) e índice HNSW doc_chunk_embedding_hnsw_idx
  (com m=16, ef_construction=64 e opclasses vector_cosine_ops); migration 0002_documentchunk_embedding_and_more
  com VectorExtension() aplicada no PostgreSQL real; VectorSearchRepository implementado em apps.intelligence.repository
  com ordenação por CosineDistance, isolamento estrito por tenant, filtro obrigatório is_current=true (ignorando
  chunks staged) e filtro opcional por edital; 70/70 pytest passando (6 novos testes de integração em
  test_vector_intelligence.py); ruff check ., django check e makemigrations --check 100% limpos.
- Task 14 evidências: GeminiEmbeddingAdapter implementado em apps.intelligence.embeddings encapsulando
  google-genai oficial; formatos documentados RETRIEVAL_DOCUMENT (com título e texto) e RETRIEVAL_QUERY;
  saída com dimensão 768 validada e qualquer discrepância de dimensão rejeitada com ValueError;
  chave de API lida estritamente de GEMINI_API_KEY do ambiente; dependências google-genai 2.23.0 e pgvector 0.5.0
  instaladas e travadas em uv.lock; 64/64 pytest passando (5 novos testes unitários em test_embeddings.py);
  ruff check ., django check e makemigrations --check 100% limpos.
- Task 13 evidências: modelo DocumentChunk com UniqueConstraint(tender, generation, chunk_index),
  modelo OutboxMessage com lease atômico e estados PENDING/PROCESSING/SENT/FAILED, serviço de chunking
  preservando página e offsets exatos (chunker.py), task Celery versionada pipeline.process_tender.v1 com
  validação de tenant direto do banco, compare-and-set de jobs stale e troca atômica de gerações staged
  para current mantendo histórico em falhas; agendamento transacional de outbox no upload de editais
  (POST /api/tenders/); relay de outbox com lease atômico e reconciliador de timeouts (outbox.py);
  migrations 0004 de tenders e 0001 de pipeline aplicadas; 59/59 pytest passando (7 novos testes de integração
  em test_document_pipeline.py); ruff check ., django check e makemigrations --check 100% limpos; 3/3 vitest limpos.
- Task 12 evidências: serviço puro de extração apps.pipeline.pdf_extractor (extract_pdf_pages, ExtractedPage,
  normalize_page_text), exceções de domínio em apps.pipeline.exceptions (PdfInvalidError, PdfEncryptedError,
  NoTextExtractedError, PageLimitExceededError, CharLimitExceededError), dependência pypdf 5.9.0 adicionada e
  bloqueada em uv.lock; offsets de code points por página normalizada; isolamento completo de HTTP/Celery;
  fixture e helpers em tests/fixtures/pdf_helpers.py; 52/52 pytest passando (7 novos testes unitários em
  tests/unit/pipeline/test_pdf_extractor.py); ruff check ., django check e makemigrations --check 100% limpos.
- Task 11 evidências: endpoint GET /api/tenders/{id}/processing-status/ implementado com
  TenderProcessingStatusSerializer (tenderId, status, progress, processedChunks, error), Retry-After: 2
  para status PENDING e PROCESSING, isolamento estrito multi-tenant (404 em cross-tenant), erro seguro
  sem stack trace em FAILED (PDF_INVALID com mensagem amigável), campos progress e processed_chunks adicionados
  ao modelo Tender com migration 0003 aplicada no PostgreSQL real; 45/45 pytest passando (6 novos testes
  em test_tender_management.py); ruff check ., django check e makemigrations --check limpos; 3/3 vitest limpos.
- Task 10 evidências: modelo IdempotencyKey com UniqueConstraint(company, user, endpoint, key),
  hash canônico hashlib.sha256(f"{sha256_hash}:{title.strip()}:{description.strip()}"), select_for_update atômico,
  reprodução 202 com mesmo edital em retries com mesmo payload, 422 UNPROCESSABLE_ENTITY em payloads com
  mesma chave e conteúdo divergente, isolamento estrito de chave por tenant e usuário; migration 0002_idempotencykey
  aplicada; 39/39 pytest passando (3 novos testes de integração em test_tender_management.py); ruff check .,
  django check e makemigrations --check 100% limpos. Checkpoint Upload contract verificado.
- Task 4 evidências: Company e User com UUIDs, slug autogerado e único, email case-insensitive
  no banco (Lower constraint) e normalizado, company obrigatória (on_delete=PROTECT, non-nullable),
  role restrito a OWNER no banco via CheckConstraint, CaseInsensitiveModelBackend com dummy password
  check para timing resistance, migration 0001_initial aplicada no PostgreSQL real, 10/10 pytest
  passaram (5 novos em test_identity_models.py), ruff check . e makemigrations --check limpos.
- Task 5 evidências: POST /api/auth/register/ com atomicidade de transação (@transaction.atomic),
  reversão da empresa em falha do usuário comprovada em teste; 409 CONFLICT em duplicação de email
  no envelope padrão; 400 VALIDATION_ERROR em payload inválido; refresh_token emitido em cookie
  httpOnly sameSite=Lax (secure fora de localhost/dev); access token 15m; 14/14 pytest passaram
  (4 novos testes em tests/integration/test_identity_tenant.py), ruff check . limpo.
- Task 6 evidências: POST /api/auth/token/ (login genérico não revela existência de email; 401
  para usuário inativo ou senha inválida), POST /api/auth/token/refresh/ (rotação de refresh em cookie,
  blacklist do anterior e reuse detection), POST /api/auth/logout/ (204 e expiração de cookie),
  GET /api/auth/me/ (identidade autenticada de usuário e empresa via Bearer), GET /api/auth/csrf/
  (emissão de token CSRF); 23/23 pytest passaram (9 novos testes cobrindo todo o contrato de sessão),
  ruff check . e manage.py check 100% limpos.
- Task 7 evidências: backend/apps/core/permissions.py implementado (get_user_company, filter_by_tenant,
  IsTenantMember); derive tenant exclusivamente de request.user; tentativa de injeção de companyId
  no payload/query é ignorada; teste de integração com duas empresas independentes comprova isolamento
  estrito na API e no ORM; 25/25 pytest passaram; 3/3 vitest passaram; frontend lint e typecheck limpos.
- Task 8 evidências: backend/apps/tenders/models.py com modelo Tender (UUID, company FK, title,
  description, status PENDING/PROCESSING/PROCESSED/FAILED com CheckConstraint, storage_key, original_filename,
  file_size, sha256, pipeline_generation, error_code, error_message); serializers.py com TenderPublicSerializer
  em camelCase; views.py com TenderListCreateView (paginação {data, pagination}, page 1-indexed, pageSize max 50,
  filtros por status e ordenação) e TenderDetailView com 404 para editais de outros tenants; migration
  0001_initial de tenders aplicada; 31/31 pytest passando (6 novos testes de integração em test_tender_management.py);
  ruff check ., django check e makemigrations --check limpos.
- Task 9 evidências: backend/apps/tenders/storage.py (LocalStorageAdapter com chave segura {company_id}/{tender_id}.pdf
  em volume privado UPLOAD_ROOT /var/lib/govintel/uploads e método delete), validators.py (validate_pdf_upload com
  verificação de não-vazio, limite 50MB, assinatura mágica b'%PDF-', cálculo de sha256), TenderListCreateView.post
  (upload multipart retornando 202 Accepted em status PENDING) e TenderDetailView.delete (204 No Content com cleanup
  automático do arquivo no storage privado); 36/36 pytest passando (5 novos testes cobrindo upload válido, arquivo vazio 400,
  magic bytes falso 400, delete com remoção de blob e delete cross-tenant 404); ruff check . e manage.py check limpos.
- Conflito: Task 1 exige iniciar aplicações cujos scaffolds são Tasks 2–3.
  Resolução registrada em docs/implementation-decisions.md antes do código.
- Git: `git rev-parse --is-inside-work-tree` falhou; sem commits possíveis.
- Comandos executados: inventário, leitura de contratos, docker version/info,
  docker desktop start, docker compose version, wsl --status.
- Runtime: seis serviços saudáveis; portas 3000/8000/5432/6379/5672/15672
  acessíveis somente por publicação 127.0.0.1. Volumes preservados no restart.
- Gates: Compose config passou; pytest 5/5 com PostgreSQL; Ruff e Django check
  passaram; HTTP 200 em /health/; Celery pong e filas duráveis confirmados.
- Backend: backend/config, apps base, tests, Dockerfile, pyproject.toml, uv.lock.
  Python 3.12.14, Django 5.2.17, Celery 5.6.3, DRF 3.16.1.
- Falha esperada RED: pytest antes do scaffold → No module named config.
- Ajuste: ownership de /app no Dockerfile para pytest cache do usuário non-root.
- Decisão resolvida: usuário autorizou 409 genérico no cadastro; exceção
  documentada. Login/refresh continuam protegidos contra enumeração.
- Frontend: Next 15.5.25, Node 24.17.0, Vitest 4.1.11, PostCSS 8.5.28 override;
  package-lock.json, scripts desabilitados. Build/dev 200, lint/typecheck,
  3 testes e npm audit zero; navegador desktop/320px, console limpo.
- Falhas resolvidas: cache non-root; TypeScript precisava /app gravável;
  chown de arquivo inexistente removido; rede data internal impedia portas do
  host, trocada por bridge com publicação loopback. Nenhum gate suprimido.

## Investigação — 2026-09-16, cadastro e login

- Sintoma reproduzido ao abrir o frontend por `http://127.0.0.1:3000`:
  o preflight para `/api/auth/csrf/` e `/api/auth/register/` falhava por CORS,
  pois somente `http://localhost:3000` estava autorizado; o formulário exibia
  a mensagem genérica de falha e nenhum usuário era criado.
- Correção aplicada: `FRONTEND_ORIGINS` aceita uma lista explícita separada por
  vírgulas; CORS e `CSRF_TRUSTED_ORIGINS` usam a mesma lista. O `.env` local e
  `.env.example` incluem `localhost` e `127.0.0.1`; deployments podem manter
  apenas a origem pública em `FRONTEND_ORIGIN` ou configurar a lista adicional.
- Evidência: preflight de loopback passou, cadastro e login via
  `http://127.0.0.1:3000` passaram; 115/115 pytest, Ruff, Django check e
  Compose config passaram; seis serviços continuam saudáveis.
- Próximo gate: repetir o fluxo no navegador usado pelo usuário, abrindo
  `http://localhost:3000` ou `http://127.0.0.1:3000`; se o email já existir,
  o cadastro responde 409 conforme decisão aprovada e o login deve usar a
  senha originalmente cadastrada.

## Investigação — 2026-09-16, cota do Gemini no processamento

- O worker recebeu `429` do `embed_content_free_tier_requests` ao usar a chave
  Gemini real local; o erro era de cota do projeto Google, não de PDF, fila ou
  autenticação. O SDK/API recomenda aguardar ou aumentar a cota para uso real.
- Para a demo local, `.env` foi ajustado para `GEMINI_API_KEY=mock`, conforme o
  contrato do MVP. API e worker foram recriados sem apagar volumes; o adapter
  determinístico mantém 768 dimensões e não faz chamadas externas.
- O único edital local marcado com erro 429 foi reencaminhado uma vez após a
  troca de provider e terminou `PROCESSED` com 224 chunks. Não houve remoção de
  arquivo ou dado.
- Evidência: E2E completo 1/1 passou após a troca; API e worker saudáveis,
  `celery inspect ping` retornou `pong`. Para voltar ao Gemini real, é preciso
  restaurar a chave e usar um projeto com cota/billing disponíveis.
## Revisão de segurança, CI/CD e dúvida adversarial — 2026-09-17

- Revisão feita com as skills `security-and-hardening`, `ci-cd-and-automation` e
  `doubt-driven-development`; nenhuma alteração de código aplicada nesta etapa.
- Runtime: `docker compose config --quiet`, seis serviços saudáveis, Django check,
  Ruff, `npm audit` (raiz/frontend) e ping do worker passaram.
- Bloqueadores confirmados: views DRF de registro/login/refresh/logout são
  `csrf_exempt` (inclusive com Origin não confiável); o identificador do login
  aceita `X-Forwarded-For` controlado pelo cliente (`NUM_PROXIES=None`); registro,
  upload e refresh não têm throttling; Redis indisponível desativa o throttling;
  rotação de refresh não rastreia família nem revoga a substituição em reuse;
  citações inválidas viram texto arbitrário e respostas sem citações seguem
  publicadas; erros internos do worker são expostos em `errorMessage`; e o relay
  do outbox/reconciliador não é iniciado automaticamente.
- CI: `backend-quality` executa toda a suíte, mas não provisiona PostgreSQL/Redis/
  RabbitMQ e usa `DATABASE_URL` com host `db`; o job falha fora do Compose. A
  auditoria local `pip-audit --strict` também falha para Pillow 11.3.0 (35
  advisories, correções a partir da série 12.x); `pyproject.toml` ainda limita
  Pillow a `<12`.
- Busca/RAG: chunks existentes permanecem com embeddings Gemini enquanto o
  runtime consulta OpenRouter; a task não grava o modelo/provider efetivo nos
  metadados do chunk e a busca não filtra por fingerprint. Há log de timeout real
  do chat OpenRouter e fallback silencioso para mock.
- Riscos adicionais para o próximo gate: `_resolve_path` aceita traversal fora do
  volume (`../../etc/passwd` resolve fora da raiz); `message`/`query` não têm
  limite de comprimento; CSP/HSTS não estão configurados no app; health só testa
  PostgreSQL; storage local não serve múltiplas réplicas.
- Git: a pasta não é um repositório Git; não foi possível verificar histórico,
  branch protection ou status checks remotos. O `.env` local contém chaves não
  vazadas neste registro e permanece ignorado; não reproduzir valores.
- Próximo gate: corrigir CSRF/refresh/throttling e CI/dependências, reindexar os
  PDFs no mesmo provider, testar citações inválidas e validar o fluxo real de
  OpenRouter antes de considerar a Fase 6 pronta.

## Estabilização de sessão, CI, provider e chat — 2026-09-17

Implementado:

- CSRF explícito nas views de mutação de autenticação, rotação de refresh com
  registro de família e revogação em reuse, throttling para cadastro, refresh e
  upload, fail-closed quando o Redis de throttling falha e `NUM_PROXIES` com
  valor seguro por configuração.
- Traversal bloqueado no storage local, mensagens de erro do pipeline mapeadas
  por códigos seguros e upload/processamento sem persistência de exceções
  arbitrárias.
- Chunks passaram a registrar provider, modelo, versão, dimensão, normalização
  e fingerprint de preprocessing; retrieval filtra pelo provider ativo.
- Citações passaram a ser fail-closed. O provider OpenRouter recebe uma única
  solicitação corretiva quando as citações não são literais; sem citação
  validada, a resposta permanece em insuficiência de evidência.
- `reindex_embeddings` foi criado com modo `--dry-run` e reindexação atômica por
  edital. Pillow foi atualizado para `>=12.3,<13` e o lockfile para 12.3.0.
- CI passou a provisionar PostgreSQL, Redis e RabbitMQ com health checks antes
  dos testes backend.

Verificado:

- `docker compose up -d --build --wait` e `docker compose config --quiet`;
  seis serviços saudáveis e `celery inspect ping` com `pong`.
- `python manage.py migrate --noinput`, `check`, `makemigrations --check`,
  Ruff e `uv run pip-audit --strict` passaram; auditoria: nenhum advisory
  conhecido.
- `151 passed` no backend; `42 passed` no frontend; lint e typecheck frontend
  passaram.
- Dry-run identificou 29 editais processados. Reindexação real concluiu os 29;
  os 55 chunks atuais estão em `openrouter/openai/text-embedding-3-small`,
  768 dimensões, versão `v1`, normalização `NFKC` e fingerprint
  `v2-pdf-layout-ocr-sentence`.
- Validação real do chat após reindexação: busca recuperou evidência e a
  resposta OpenRouter concluiu com `6` citações validadas e resposta de 697
  caracteres. Nenhum conteúdo de edital, prompt, token ou chave foi registrado.

Pendências conhecidas: o relay do outbox/reconciliador ainda não possui caller
periódico de produção; storage local continua inadequado para múltiplas
réplicas; JWT ainda não usa issuer/audience dedicados; publicação/deploy e
revisão humana permanecem fora deste gate.

## Correção de CSRF entre hosts locais — 2026-09-17

- Sintoma reproduzido: cadastro/login abertos por um hostname local diferente
  do hostname configurado para a API retornavam `403 CSRF verification failed`.
- Causa: `localhost` e `127.0.0.1` são sites diferentes para a política de
  cookies. Com `SameSite=Lax`, o cookie CSRF não acompanhava a chamada feita
  entre esses hosts, embora ambos estivessem autorizados em CORS/CSRF.
- Correção: `frontend/lib/api-url.ts` alinha automaticamente hosts locais da
  API ao hostname da página; URLs externas de produção permanecem explícitas.
  A documentação do README foi atualizada.
- Verificação: testes frontend `43 passed`, lint/typecheck e build Next
  passaram; Playwright confirmou cadastro e login sem 403 em
  `http://127.0.0.1:3000` e `http://localhost:3000` (2 testes por host).

## Redesign frontend — 2026-09-17

- [x] Direção visual registrada em `docs/frontend/design-plan.md`: centro de
  inteligência de licitações, editorial, preciso e orientado por evidências.
- [x] Guias de tipografia, cor/contraste, interação, movimento e UX writing
  criados em `docs/frontend/`.
- [x] Fundação visual refeita em `frontend/app/globals.css`: tokens papel,
  tinta, teal institucional, dourado de sinal, superfícies, foco visível,
  responsividade e `prefers-reduced-motion`.
- [x] Home e autenticação receberam shell de produto; dashboard, busca e chat
  usam superfícies mais quietas, rail de evidência, estados semânticos e
  controles acessíveis sem alterar IDs nem contratos de API.
- [x] `frontend/components/product-brand.tsx` concentra o wordmark e o
  marcador visual compartilhado entre entradas públicas.
- [x] Revisão no navegador real após rebuild do frontend: home, login,
  dashboard vazio, busca vazia e chat com painel de fontes abriram sem erro
  visual em viewport desktop 1280x720.
- [x] Capturas reproduzíveis salvas em `docs/frontend/evidence/` para home,
  login, dashboard vazio, busca vazia e chat vazio.
- [x] Gates: 43 testes Vitest em execução serial, lint/Prettier, typecheck e
  build Next passaram. O teste de citações também passou isoladamente; a
  execução paralela ocasionalmente excede o timeout de 5s por contenção.

Próximo gate: revisão humana em viewport móvel e validação do fluxo autenticado
com dados de demonstração antes de merge ou deploy.

## Migração OpenCode + embeddings locais — 2026-09-18

- Implementado: `LLM_PROVIDER` e `EMBEDDING_PROVIDER` independentes; padrão
  OpenCode Zen com `deepseek-v4-flash` e embeddings locais
  `intfloat/multilingual-e5-base`, CPU, 768D, batch 32 e cache persistente.
- O adapter local usa os prefixos oficiais `passage:`/`query:`, normalização
  L2, carregamento lazy com cache por processo e fingerprint persistível.
  Providers Gemini/OpenRouter permanecem somente por seleção explícita.
- OpenCode valida a disponibilidade exata do modelo no endpoint `/models`, usa
  timeout/retry limitados e mapeia falhas para erros sanitizados. Não há
  fallback implícito para outro provider.
- Retrieval agora filtra todos os metadados do espaço vetorial. O novo
  `reindex_embeddings` faz staging do corpus, promoção all-or-nothing e
  oferece rollback explícito por geração/tender.
- Evidência final desta etapa: imagens API/worker reconstruídas, `check`,
  migrations check, Ruff e 167 testes backend passaram; frontend lint,
  typecheck, build e 43 testes passaram; Compose config passou.
- Dry-run local real: 29 editais e 55 chunks current em 0,03 s. Reindex local
  real: 29 editais, 55→55 chunks, promoção concluída em 88,88 s, memória abaixo
  do limite de 2 GiB. Verificação no banco: 55 current homogêneos com provider
  `local`, modelo E5, versão `main`, dimensão 768, L2 e fingerprint único; duas
  gerações antigas permanecem preservadas.
- Auditoria: `pip-audit` direto não aceita `torch+cpu` no índice PyPI; o CI foi
  ajustado para auditar o requirements exportado sem esse wheel e exigir a
  variante `+cpu` separadamente. Essa auditoria retornou zero vulnerabilidades
  conhecidas. Nenhum push/deploy foi executado.
- Modelo de chat atualizado para `deepseek-v4-flash`, listado no catálogo Zen
  e compatível com Chat Completions. Após rebuild, teste focado (10), suíte
  backend (167), Ruff e Django check passaram; embeddings não foram
  reindexados porque a mudança não altera o modelo vetorial.
- README ampliado com explicação detalhada da stack, arquitetura, pipeline
  assíncrono, RAG, embeddings, segurança, contratos, operação, testes e
  decisões conceituais; Prettier passou em `README.md`.
