# Revisão adversarial: decisões e correções

Esta revisão foi feita contra o contrato do MVP e os documentos de arquitetura, API e segurança. O objetivo é impedir que garantias sejam apenas afirmações no texto.

## Achados acionáveis incorporados

| Área | Falha possível | Correção de contrato |
|---|---|---|
| Embeddings | Upgrade muda o espaço vetorial | Persistir modelo, versão, dimensão, normalização e fingerprint de preprocessing; re-embedding é migration explícita |
| HNSW/tenant | ANN pode filtrar tenant depois da travessia | Índice B-tree por tenant, overfetch configurável, teste de recall por tenant e fallback exato para dataset pequeno |
| Worker | Redelivery duplica chunks ou sobrescreve estado novo | Chave determinística de chunk, upsert transacional, compare-and-set por geração e lease/heartbeat |
| Fila | Tender fica `PENDING` se publicação falhar | Outbox transacional e dispatcher/reconciler; status de enqueue observável |
| Idempotência | Retry de outro usuário/endpoint colide | Chave escopada por tenant, usuário e endpoint; hash do body, retenção e cleanup documentados |
| Status | Worker morto deixa `PROCESSING` eterno | Lease expirável, heartbeat e reconciliador que reencaminha ou finaliza com código seguro |
| Tenant | Busca é apenas uma das superfícies | Autorização também em status, arquivos, chunks, chat, citações, cache, tasks, logs e endpoints de debug |
| Cache | Resultado antigo ou de escopo errado | Namespace inclui tenant, usuário/role, revisão dos dados, modelo e índice; bump de revisão invalida |
| PDF | Parser pode consumir memória/CPU ou aceitar arquivo malformado | Limites de bytes/páginas/texto, timeout, processo isolado, cleanup e códigos de falha |
| Citações | LLM pode citar chunk irrelevante ou inventar ID | Saída estruturada com IDs allowlisted, validação contra retrieval e quote exata persistida |
| Prompt injection | Texto do edital pode instruir o modelo | Contexto delimitado como dados, zero ferramentas no chat, limites de tokens e nenhuma saída executável |
| JWT/cookies | Refresh cookie pode sofrer CSRF/replay | CSRF token/origin check, rotação, revogação, reuse detection, issuer/audience e logout definidos |
| API | DRF pode escapar do envelope de erro | Exception handler global e conversão de campos públicos para camelCase |
| Compose/CI | Health check verde sem migration/worker pronto | Readiness de schema, filas declaradas, smoke test, graceful shutdown e resource limits |

## Trade-offs aceitos para o MVP

- PDFs escaneados agora passam por OCR local (Tesseract, pacote `por`) em páginas sem camada de texto; sem toolchain ou com `OCR_ENABLED=false`, o sistema finaliza com `NO_TEXT_EXTRACTED` e mensagem visível (atualizado em 2026-09-17 a pedido do usuário; antes, nenhum OCR era feito).
- Storage local é aceitável em demo, desde que a abstração impeça caminhos públicos e a retenção seja documentada.
- Para poucos chunks, busca exata pode ser usada como fallback de verificação; HNSW continua obrigatório e é testado separadamente.
- Não haverá ferramentas externas no RAG; isso reduz agência e elimina superfícies SSRF/execução.

## Gate antes de implementar RAG

- [x] Definir outbox e reconciliador da fila.
- [x] Definir schema estruturado de resposta/citação.
- [x] Definir quotas do parser e política de `PROCESSING` stale.

## Follow-up adversarial — 2026-09-17

As correções foram reavaliadas contra os mesmos riscos. CSRF, reuse detection,
throttling fail-closed, traversal, mensagens sanitizadas, provider metadata,
reindexação homogênea e citações fail-closed têm testes de integração e gates
operacionais verdes. O provider OpenRouter recebeu uma segunda solicitação
somente quando a primeira falhou na validação literal; nenhuma citação divergente
é promovida para a resposta persistida. Permanecem riscos aceitos e explicitados
para a próxima fase: caller periódico do outbox/reconciliador, storage
compartilhado para réplicas e issuer/audience dedicados no JWT.

## Follow-up adversarial — 2026-09-18

O risco de mistura entre modelos foi reavaliado: o retrieval exige a identidade
completa do vetor e a busca/cache não aceitam metadata parcial. A reindexação
local foi executada com staging corpus-wide (29 editais, 55 chunks, 88,88 s),
com duas gerações antigas preservadas. O caminho OpenCode valida o modelo exato,
limita retry corretivo de citações a uma tentativa e falha fechado quando não
há prova literal. O catálogo público do OpenCode Zen observado nesta data lista
`deepseek-v4-flash` no endpoint compatível com Chat Completions; a aplicação
continua validando o ID exato e rejeitando qualquer alias ou fallback.
