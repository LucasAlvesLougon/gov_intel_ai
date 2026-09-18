# Deploy da demonstração

## Alvo escolhido

O alvo de preparação é o Render, usando serviços Docker ligados ao repositório:

| Componente    | Serviço Render                                     | Persistência/conexão                                      |
| ------------- | -------------------------------------------------- | --------------------------------------------------------- |
| Next.js       | Web Service a partir de `frontend/Dockerfile`      | filesystem efêmero; assets são gerados no build           |
| Django/DRF    | Web Service a partir de `backend/Dockerfile`       | conecta ao Postgres, Redis e RabbitMQ pela rede privada   |
| Celery        | Background Worker usando a mesma imagem do backend | mesma configuração de banco, Redis e broker               |
| PostgreSQL 16 | Render Postgres gerenciado                         | habilitar `CREATE EXTENSION vector;` antes das migrations |
| Redis         | Render Key Value compatível com Redis              | URL privada com TLS quando fornecida pelo serviço         |
| RabbitMQ 4    | Private Service Docker com disco persistente       | porta AMQP 5672 somente na rede privada                   |

Render suporta imagens Docker para web services e background workers, health
checks HTTP e variáveis/secrets no ambiente do serviço. O Postgres gerenciado
suporta `pgvector`; RabbitMQ pode ser executado como serviço privado Docker
com disco em `/var/lib/rabbitmq`. Consulte a documentação atual do provedor
antes de escolher região e plano:

- [Web Services e Docker](https://render.com/docs/web-services)
- [Docker no Render](https://render.com/docs/docker)
- [Health checks](https://render.com/docs/health-checks)
- [Postgres e extensões](https://render.com/docs/postgresql-extensions)
- [RabbitMQ no Render](https://render.com/docs/deploy-rabbitmq)
- [Discos persistentes e limitações](https://render.com/docs/disks)

Esta etapa prepara a configuração; não publica nada. A workspace ainda não
possui remoto Git configurado e o deploy continua sujeito a uma autorização
explícita.

## Limitações que bloqueiam um deploy direto

O Compose local compartilha o volume `private_uploads` entre `api` e `worker`.
Discos persistentes do Render são acessíveis por uma única instância de serviço
e não podem ser lidos por outro serviço, portanto
o pipeline de produção precisa trocar `LocalStorageAdapter` por um bucket
S3-compatible privado (ou outro storage compartilhado) antes de executar o
worker fora da mesma máquina. O bucket deve manter a chave
`{companyId}/{tenderId}.pdf`, bloquear acesso público e permitir deleção
idempotente. Não use o filesystem efêmero para PDFs.

O RabbitMQ gerenciado não é assumido pelo plano; a alternativa documentada é
um Private Service com disco. Se a disponibilidade desse serviço não atender
ao SLA da demo, use um broker AMQP externo e forneça apenas a URI como secret.

## Variáveis e serviços

Configure as variáveis no painel do Render ou em um Environment Group. Nunca
as coloque em `render.yaml`, no Dockerfile, no repositório ou em logs.

**API e worker:** `DJANGO_SECRET_KEY`, `DATABASE_URL`, `REDIS_URL`,
`CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, `FRONTEND_ORIGIN` e, quando
necessário, `FRONTEND_ORIGINS` (lista separada por vírgulas),
`DJANGO_ALLOWED_HOSTS`, `LLM_PROVIDER`, `OPENCODE_API_KEY`,
`OPENCODE_BASE_URL`, `OPENCODE_CHAT_MODEL`, `EMBEDDING_PROVIDER`,
`LOCAL_EMBEDDING_MODEL`, `LOCAL_EMBEDDING_DIMENSIONS`,
`LOCAL_EMBEDDING_DEVICE`, `LOCAL_EMBEDDING_BATCH_SIZE`, `UPLOAD_ROOT` e
`UPLOAD_RETENTION_DAYS`. O cache de modelo deve ser um volume privado
compartilhado entre API e worker.

O modelo local é CPU-first e pode consumir memória significativa; o Compose
reserva 2 GiB para API/worker e mantém um processo HTTP/worker por serviço para
evitar carregar múltiplas cópias. Rode `reindex_embeddings --dry-run` antes da
execução real e guarde a saída operacional (sem conteúdo de PDF). Uma falha
preserva a geração current; rollback explícito usa a geração anterior mantida
no banco. Antes de um rollback para uma geração produzida por outro provider,
restaure também `EMBEDDING_PROVIDER` e seus metadados de modelo; o retrieval
permanece fail-closed quando a configuração ativa não coincide com a geração.

**Frontend:** `NEXT_PUBLIC_API_BASE_URL` aponta para a URL pública da API e
`API_BASE_URL` aponta para a URL privada da API quando o servidor Next precisar
de acesso interno. `NEXT_PUBLIC_API_BASE_URL` é incorporada no build e não é
um segredo.

Configure o Web Service da API com health check `/health/`. O Dockerfile já
executa migrations e inicia Gunicorn usando `PORT` (ou 8000 localmente). O
Background Worker deve sobrescrever o comando para:

```text
python manage.py declare_queues && celery -A config worker --loglevel=WARNING --concurrency=2 --hostname=worker@%h
```

O frontend usa o `CMD` da imagem e deve receber a URL pública da API como
argumento de build. Depois de criar o Postgres, conecte-se com o comando PSQL
do painel e execute uma vez:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

## Smoke test e promoção

Após cada deploy, registre o identificador da versão e execute:

```text
curl --fail --silent --show-error https://<api-host>/health/
curl --fail --silent --show-error https://<frontend-host>/
```

Em seguida, valide manualmente o fluxo registro → upload → processamento →
busca → chat e confirme no painel que o worker consumiu a fila. O health check
deve responder em até cinco segundos, sem status 5xx; falha cancela a
promoção. Observe logs, erros, latência, profundidade da fila e espaço do
storage na primeira hora. Logs não devem conter credenciais, tokens, prompts ou
PDFs integrais.

## Rollback

Mantenha pelo menos um deploy bem-sucedido anterior e, para imagens em registry,
publique por digest imutável. No Render, abra **Deploys**, selecione o último
deploy saudável e use **Rollback**; o provedor reutiliza o artefato anterior.
Depois repita os dois smoke tests e o fluxo crítico. A documentação do Render
explica as diferenças entre rollback de código, variáveis, discos e imagens:
[Rollbacks](https://render.com/docs/rollbacks).

Não reverta migrations destrutivas durante uma indisponibilidade. Preserve o
backup do Postgres, corrija o código e faça uma migration compatível para
frente; restaure snapshot somente após avaliar perda de dados. Se o problema
for uma variável ou segredo, corrija o Environment Group e faça novo deploy.
