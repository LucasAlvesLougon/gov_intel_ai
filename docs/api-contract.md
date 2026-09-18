# Contratos de interfaces

Este documento é a fonte de verdade entre Next.js, DRF, Celery, Redis e PostgreSQL. Campos JSON públicos usam `camelCase`; Python e banco podem usar `snake_case` internamente.

## Envelope de erro

Todo erro HTTP usa a mesma forma:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "O arquivo deve ser um PDF",
    "details": {}
  }
}
```

Mapeamento: `400` payload/formato inválido, `401` não autenticado, `403` sem autorização, `404` recurso inexistente ou invisível ao tenant, `409` conflito/duplicação, `422` semanticamente inválido, `429` throttling e `500` erro interno sem detalhes de infraestrutura.

## REST público

| Método | Rota | Entrada | Saída |
|---|---|---|---|
| POST | `/api/auth/register/` | `companyName`, `email`, `password` | usuário, empresa, accessToken; refresh somente em cookie |
| GET | `/api/auth/csrf/` | — | csrfToken e cookie CSRF httpOnly |
| POST | `/api/auth/token/` | `email`, `password` | access; define refresh cookie |
| POST | `/api/auth/token/refresh/` | refresh cookie | access; rotate cookie |
| POST | `/api/auth/logout/` | refresh cookie | 204; revoga cadeia e remove cookie |
| GET | `/api/auth/me/` | — | usuário e empresa autenticados |
| GET | `/api/tenders/` | `page`, `pageSize`, `status`, `sortBy`, `sortOrder` | `{ data, pagination }` |
| POST | `/api/tenders/` | multipart PDF + metadados | edital e `202` |
| GET | `/api/tenders/{id}/` | — | edital |
| GET | `/api/tenders/{id}/processing-status/` | — | status e progresso |
| POST | `/api/search/semantic/` | `query`, `tenderId?`, `topK?`, `page?`, `pageSize?` | `{ data, pagination }` |
| POST | `/api/tenders/{id}/chat/` | `conversationId?`, `message` | resposta e citações |

Recursos protegidos e `/me/` exigem `Authorization: Bearer <accessToken>`.
`/health/` e `/api/auth/csrf/` são públicos. Registro/login não exigem access;
refresh/logout usam cookie, sem depender de access expirado. Mutações de sessão
exigem CSRF token e Origin permitido (ou Referer com a mesma origem), inclusive
registro/login para impedir login CSRF. GET csrf fornece o token para
`X-CSRFToken`; refresh nunca aparece em JSON. Cadastro duplicado mantém 409
genérico pela exceção aprovada em 2026-09-16.

Listas são paginadas desde o início:

```json
{
  "data": [],
  "pagination": { "page": 1, "pageSize": 20, "totalItems": 0, "totalPages": 0 }
}
```

`page` começa em 1; `pageSize` padrão é 20 e máximo 50; `topK` padrão é 8 e máximo 50; ordenação padrão é `createdAt desc`. O overfetch interno é limitado e não altera o número de itens retornados. O frontend não deve depender da ordem incidental do banco.

### Upload e idempotência

`POST /api/tenders/` exige `Idempotency-Key`, gerado pelo cliente e reutilizado em retries. O hash é calculado sobre representação canônica (bytes do PDF em streaming + metadados normalizados e ordenados), nunca sobre boundary ou bytes crus do multipart. A chave é única por empresa, usuário e endpoint. A primeira chamada retorna `202 Accepted`; repetição equivalente reproduz o mesmo edital; payload canonicamente diferente retorna `422`; duplicata ainda em andamento retorna `202` e a mesma URL de status.

O servidor deve reclamar a chave atomically por constraint única em PostgreSQL antes de agendar a task. O registro deve sobreviver ao maior caminho de retry da fila.

O registro de idempotência é escopado por `companyId`, `userId` e endpoint, armazena hash do body e possui retenção/cleanup maior que o retry máximo e qualquer replay de dead-letter.

## Estados do pipeline

```text
PENDING → PROCESSING → PROCESSED
                     ↘ FAILED
```

Somente o worker pode mudar `PROCESSING`, `PROCESSED` e `FAILED`. O endpoint de upload cria `PENDING`. `FAILED` inclui `errorCode` seguro e não inclui stack trace ou credenciais.

`PROCESSING` possui lease e heartbeat. Um reconciliador detecta lease expirado e reencaminha o job ou finaliza com `PROCESSING_TIMEOUT`; task antiga não pode sobrescrever uma geração mais nova.

O status retorna:

```json
{
  "tenderId": "uuid",
  "status": "PROCESSING",
  "progress": 65,
  "processedChunks": 42,
  "error": null
}
```

Polling recomendado: primeira consulta após 1 segundo e depois a cada 2 segundos, por no máximo 30 tentativas. Estados `PROCESSED` e `FAILED` são terminais; timeout do cliente não altera o job. O endpoint pode retornar `Retry-After` durante `PENDING`/`PROCESSING`.

## Contrato Celery/RabbitMQ

- Task versionada: `pipeline.process_tender.v1`.
- Payload: `{ "tenderId": "uuid", "jobId": "uuid" }`.
- O worker lê o arquivo pelo `tenderId`; nunca recebe conteúdo bruto na mensagem.
- `Tender.storageKey` aponta para volume privado; o adapter de storage valida existência, tenant e cleanup. O nome original é apenas metadado de apresentação.
- Exclusão de edital cria evento de cleanup; um worker remove blob, chunks, cache e conversas com retry/reconciliação. Uma varredura periódica encontra e remove blobs órfãos conforme retenção.
- Ao consumir a task, o worker consulta o banco e deriva/valida `company_id` do edital; nunca confia em tenant enviado na mensagem.
- Ao consumir a task, o worker consulta o banco e deriva/valida `company_id` do edital; nunca confia em tenant enviado na mensagem.
- Entrega é at-least-once; a task deve ser idempotente por `jobId`.
- Retry exponencial limitado; falha finaliza em `FAILED`.
- Ack somente após persistir estado e chunks.
- Publicação é feita por outbox transacional; falha do broker não deixa `PENDING` órfão.
- Filas são duráveis e possuem dead-letter para poison messages.
- Outbox rows têm `status`, `attempts`, `leaseUntil` e `nextAttemptAt`; o relay reclama uma row com lease atômico, publica com publisher confirm, marca `SENT` e reprocessa leases expirados. Duplicatas são absorvidas pela idempotência do `jobId`.
- Exchange, queue e mensagens usam `durable=true`/`delivery_mode=2`; publisher confirms são verificados após restart do broker. Se o processo cair depois do confirm e antes de marcar `SENT`, o relay republica e a task idempotente absorve a duplicata.

## Contrato Redis

- Busca: `govintel:v1:semantic:{companyId}:{scope}:{dataRevision}:{embeddingVersion}:{indexVersion}:{sha256(canonicalQuery+filters)}`.
- TTL inicial: 5 minutos.
- Nunca aceitar `companyId` do cliente para compor a chave.
- Incrementar `dataRevision` após upload, reprocessamento, alteração de permissão ou exclusão; isso invalida respostas antigas sem depender de varredura de chaves.
- `dataRevision` pertence à empresa e também é incrementada quando conversa/permissão muda; cache nunca sobrevive a uma troca de escopo.
- `scope` inclui usuário/role quando a resposta não for compartilhável por toda a empresa.
- Throttling usa namespace separado: `govintel:v1:throttle:{userId}:{endpoint}`.

## Contrato PostgreSQL/pgvector

- `DocumentChunk.embedding` é `vector(768)`.
- Busca usa distância cosseno e índice HNSW.
- `companyId` e `tenderId` são filtros obrigatórios antes da ordenação vetorial.
- Citações são derivadas de `chunkId`, `pageNumber` e `content`, nunca geradas pelo LLM.
- A autorização também se aplica a status, arquivos, chunks, conversas, citações, cache, tasks e endpoints administrativos/debug.
- Qualquer endpoint administrativo/debug fica desabilitado por padrão no ambiente de demo ou exige role explícita.

## Contrato Docker Compose

Serviços operacionais obrigatórios:

| Serviço | Responsabilidade | Health/depends_on |
|---|---|---|
| `db` | PostgreSQL + pgvector | healthcheck `pg_isready` |
| `redis` | cache, throttling e result backend opcional do Celery | healthcheck `redis-cli ping` |
| `rabbitmq` | broker | healthcheck `rabbitmq-diagnostics ping` |
| `api` | Django/DRF HTTP | depende de db, redis e rabbitmq saudáveis |
| `worker` | Celery | depende de db, redis e rabbitmq saudáveis |
| `frontend` | Next.js | depende de `api` |

Variáveis obrigatórias: `DATABASE_URL`, `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, `DJANGO_SECRET_KEY` e `API_BASE_URL`.
Em produção, `LLM_PROVIDER=opencode` exige `OPENCODE_API_KEY`,
`OPENCODE_BASE_URL` HTTPS e `OPENCODE_CHAT_MODEL` listado pelo endpoint
`/models`. O padrão de embeddings é local: `EMBEDDING_PROVIDER=local`,
`LOCAL_EMBEDDING_MODEL=intfloat/multilingual-e5-base`,
`LOCAL_EMBEDDING_DIMENSIONS=768`, `LOCAL_EMBEDDING_DEVICE=cpu` e
`LOCAL_EMBEDDING_BATCH_SIZE=32`. Providers legados só são usados quando
selecionados explicitamente.

Cada citação aceita pelo caminho OpenCode contém `documentId`, `chunkId`,
`pageNumber` e `quote`; o backend também pode validar offsets. A citação é
descartada se o chunk não pertencer ao tenant autenticado, se a página não
coincidir ou se o quote não for substring exata do texto persistido.

O README deve fornecer os comandos `docker compose up -d`, `docker compose exec api python manage.py migrate` e `docker compose logs -f worker`.
