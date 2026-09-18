# Contrato de CI/CD e ambiente local

Este documento define os gates operacionais. Os nomes de serviços e comandos são parte do contrato consumido pelo README, CI e desenvolvedores.

## Compose local

| Serviço | Porta local | Health check | Dependências |
|---|---:|---|---|
| `db` | 5432 | `pg_isready -U govintel_user -d govintel_db` | — |
| `redis` | 6379 | `redis-cli ping` | — |
| `rabbitmq` | 5672/15672 | `rabbitmq-diagnostics -q ping` | — |
| `api` | 8000 | `GET /health/` esperando `200` | `db`, `redis`, `rabbitmq` saudáveis |
| `worker` | — | `celery -A config inspect ping` ou equivalente | `db`, `redis`, `rabbitmq` saudáveis |
| `frontend` | 3000 | `GET /` esperando `200` | `api` saudável |

O Compose deve usar volumes nomeados para PostgreSQL e não deve fixar `container_name`, evitando colisões em CI e em múltiplos worktrees. Serviços internos usam nomes DNS do Compose; o frontend usa `API_BASE_URL` configurável.

O `api` executa migrations como etapa explícita de startup antes do health check. O worker inicia somente depois do schema, filas e exchange duráveis estarem declarados. O outbox relay inicia com o worker e possui shutdown gracioso. Cada serviço tem limites de CPU/memória e usuário não-root quando a imagem permitir.

## Comandos locais

```text
docker compose config
docker compose up -d
docker compose ps
docker compose exec api python manage.py migrate
docker compose exec api python manage.py check
docker compose exec api pytest
docker compose exec api ruff check .
docker compose exec frontend npm run lint
docker compose exec frontend npm run typecheck
docker compose exec frontend npm test -- --coverage
docker compose run --rm frontend npm run build
npx playwright test e2e/govintel-flow.spec.ts
docker compose logs -f frontend
docker compose logs -f worker
docker compose down
```

O README deve indicar o diretório de execução de cada comando e não pode referenciar serviços inexistentes.

## Gates do CI

Executar em todo `pull_request` e em `push` para `main`:

1. Backend lint: Ruff.
2. Frontend lint: ESLint/Prettier check.
3. Frontend typecheck: `tsc --noEmit`.
4. Unit tests: backend e frontend com cobertura.
5. Integration tests: pgvector, Redis e RabbitMQ saudáveis, migrations aplicadas e filas declaradas.
6. Build: imagens Docker e `next build`.
7. E2E: Playwright com fixture PDF e provider de IA mockado para alterações de API, pipeline, RAG ou frontend; condicional para docs-only.
8. Security audit: auditoria nativa de Python e npm, sem remediation forçada.

Como `torch==...+cpu` vem do índice oficial do PyTorch e não é publicado no
PyPI, o gate Python exporta o lock sem esse wheel, executa
`pip-audit --strict --disable-pip` sobre todos os demais pacotes pinados e
valida separadamente que o torch instalado termina em `+cpu`. Isso mantém a
origem CPU explícita sem ignorar vulnerabilidades nos demais pacotes.

Nenhum gate pode ser ignorado por flag, supressão ou exclusão de teste. Status checks devem ser obrigatórios na branch `main`, com ao menos uma aprovação e sem force-push.

## Instalação reprodutível

- Backend deve ter um único arquivo de dependências/lockfile definido.
- Frontend deve ter um único lockfile e usar `npm ci` no CI.
- Scripts de instalação de dependências ficam bloqueados até revisão explícita.
- Versões de Python e Node devem ser fixadas nos manifests e no workflow.

## Secrets e ambientes

- `.env.example` é versionado; `.env`, `.env.local` e secrets de produção não.
- CI usa apenas secrets de teste separados de produção.
- Deploy usa secret manager da plataforma.
- Chaves não aparecem em logs, artefatos ou mensagens de erro.

## Deploy e rollback

- Pull requests não fazem deploy de produção.
- Merge em `main` pode publicar staging após todos os gates.
- Produção exige gatilho manual ou aprovação explícita.
- Cada deploy registra versão/commit e mantém uma versão anterior restaurável.
- Falha de health check ou smoke test impede promoção.
- Rollback aponta para uma imagem/commit anterior.

## Critérios de conclusão

- [x] CI roda em PR e push para `main`.
- [ ] Todos os gates são required checks (configuração de branch protection aguarda um remoto GitHub).
- [x] Compose sobe com health checks verdes.
- [x] README reproduz os comandos locais.
- [x] Auditorias não possuem vulnerabilidades críticas/altas alcançáveis sem mitigação.
- [x] Deploy tem smoke test e rollback documentado.

Evidência 2026-09-17: workflow `.github/workflows/ci.yml`, Dependabot,
auditorias locais e builds foram verificados. O único item pendente é a
configuração administrativa de required checks na branch `main`, impossível
sem um repositório remoto; o workflow falha por padrão quando qualquer gate
falha.
