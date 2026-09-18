# GovIntel AI — instruções de implementação

## Objetivo e stack
Entregar o MVP demonstrável: empresa/usuário → autenticação → PDF → pipeline
assíncrono → embeddings → busca → chat com citações verificáveis.
Obrigatórios: Python, Django, DRF, SimpleJWT, Celery; Next.js 15/TypeScript;
PostgreSQL 16/pgvector/HNSW, Redis, RabbitMQ, Docker Compose;
LangChain, Gemini Embedding 2 (`google-genai`, 768 dimensões), Gemini ou Groq.

## Autoridade e referências
Instruções explícitas do usuário > contratos API/segurança > specs de módulo >
SPEC.md > CAPABILITY-MAP.md > tasks/plan.md > tasks/todo.md > inferências.
Ler context.md e memory.md ao retomar. Consultar SPEC-*.md da capability,
docs/api-contract.md, docs/security-threat-model.md, docs/ci-cd-contract.md,
docs/adversarial-review.md, docs/architecture.md e docs/demo-script.md.
Registrar conflitos antes de implementar; preservar critérios e evidências.

## Comandos (na raiz)
- `docker compose config --quiet` valida sem imprimir valores de secrets.
- `docker compose up -d --build` inicia; `docker compose ps` verifica estado.
- `docker compose exec api python manage.py check`
- `docker compose exec api python manage.py migrate`
- `docker compose exec api pytest` e `docker compose exec api ruff check .`
- `docker compose exec frontend npm run lint` / `npm run typecheck` / `npm test`
- `docker compose run --rm frontend npm run build`
- `docker compose logs -f worker` (nunca registrar payloads privados).
Comandos de aplicação dependem dos scaffolds das Tasks 2–3; não estão
verificados até constarem como tal em context.md.

## Convenções e segurança
JSON camelCase, Python snake_case; erros `{error: {code, message, details}}`;
listas `{data, pagination}`. page ≥ 1, pageSize 20/máximo 50, topK 8/máximo 50.
Validar toda entrada no backend. Tenant vem de request.user; worker revalida
no banco. Serviços de domínio não retornam HTTP. Usar ORM parametrizado.
Access em memória, refresh protegido com rotação/blacklist/reuse/CSRF.
Storage privado por chave; nenhuma execução de PDF ou saída de LLM.
Logs sem credenciais, tokens, PII desnecessária, PDFs/prompts/respostas integrais.
Preservar lockfiles; providers mockados no CI; documentação oficial para APIs.

## Processo e limites
- **Always:** tarefas incrementais na ordem aprovada; testes antes de lógica;
  verificar checkpoint antes da próxima capability; revisar alterações;
  atualizar checkbox apenas com evidência. Não reduzir gates.
- **Ask first:** push, deploy, infraestrutura compartilhada, ações destrutivas,
  remoção de componente obrigatório ou mudança material fora do contrato.
  A implementação local descrita pelo usuário já está autorizada, inclusive
  dependências, schema inicial, auth, upload, throttling e CI especificados.
- **Never:** secrets no Git/localStorage/logs; CORS wildcard com credentials;
  testes removidos/ignorados para passar; citações inventadas; fake readiness;
  `git reset --hard`, `git checkout --`, force-push; deploy sem autorização.

## Git e contexto
Verificar se há Git antes de commit; preservar arquivos desconhecidos.
Commit pequeno por checkpoint verificado se o diretório for repositório Git.
Sem push automático. Não inventar autoria nem configurar identidade global.
context.md: estado operacional curto, task, dependências, próximo gate,
comandos, falhas e decisões abertas. Atualizar a cada task.
memory.md: append-only, com decisões, tarefas verificadas, lições e riscos
datados; não registrar secrets nem dados privados. Atualizar tasks/todo.md e
tasks/plan.md com evidência e distinguir implementação de execução verificada.
