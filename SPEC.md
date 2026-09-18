# Spec: GovIntel AI

## Objective

Construir um projeto de portfólio demonstrável que permita criar uma empresa, enviar um PDF de edital, acompanhar processamento assíncrono, pesquisar conteúdo por significado e conversar com o edital recebendo respostas com documento, página e trecho citados.

## Tech Stack

- Backend: Python, Django, Django REST Framework, SimpleJWT, Celery.
- Frontend: Next.js 15, TypeScript.
- Dados: PostgreSQL 16 com pgvector e índice HNSW.
- Infraestrutura: Docker Compose, RabbitMQ e Redis.
- IA: OpenCode Zen para LLM via endpoint OpenAI-compatible; embeddings locais
  `intfloat/multilingual-e5-base` em CPU, 768 dimensões, com providers legados
  disponíveis somente por seleção explícita.
- Testes: pytest/pytest-django, Vitest/React Testing Library e Playwright.

## Commands

Os comandos definitivos devem ser confirmados na implementação, mas o contrato esperado é:

```text
docker compose up -d
docker compose exec api python manage.py migrate
docker compose exec api pytest
docker compose exec api ruff check .
docker compose exec frontend npm run dev
docker compose exec frontend npm run build
docker compose exec frontend npm test
```

## Project Structure

```text
backend/config/              # Configuração Django, Celery e URLs
backend/apps/core/           # Identity e tenant
backend/apps/tenders/        # Editais e uploads
backend/apps/pipeline/       # Tasks, extração e chunking
backend/apps/intelligence/   # Embeddings, vetores e busca
backend/apps/conversations/  # Chat e citações
backend/tests/               # Testes unitários e integração
frontend/app/                # Rotas Next.js
frontend/components/         # Componentes reutilizáveis
frontend/lib/                # Cliente HTTP e tipos
frontend/tests/              # Testes de UI
e2e/                         # Fluxos Playwright
docs/                        # Arquitetura e roteiro da demo
tasks/                       # Plano e tarefas
```

Contratos públicos e de infraestrutura ficam em [docs/api-contract.md](docs/api-contract.md).
Controles e ameaças ficam em [docs/security-threat-model.md](docs/security-threat-model.md).
Gates de CI/CD e operações ficam em [docs/ci-cd-contract.md](docs/ci-cd-contract.md).
Achados da revisão adversarial ficam em [docs/adversarial-review.md](docs/adversarial-review.md).

## Code Style

Backend usa Ruff e nomes Python convencionais; frontend usa TypeScript, ESLint e Prettier. Componentes React ficam em PascalCase e serviços de domínio devem ser explícitos.

```python
class TenderViewSet(ModelViewSet):
    serializer_class = TenderSerializer

    def get_queryset(self):
        return Tender.objects.filter(company=self.request.user.company)
```

Validação ocorre nas fronteiras da API. O tenant é derivado do usuário autenticado, nunca de um `company_id` confiado no payload.

## Testing Strategy

- Unitários: regras de domínio, chunking, estados e montagem de prompts.
- Integração: API, banco, pgvector, Redis, RabbitMQ e Celery.
- E2E: cadastro → upload → processamento → busca → chat com citação.
- Todo fluxo crítico deve ter teste automatizado; incluir teste de isolamento entre duas empresas e teste de grounding das citações.

## Boundaries

- **Always:** validar entradas, filtrar pelo tenant, executar testes afetados, usar cookies/sessões conforme a threat model, atualizar a spec quando decisões mudarem e manter secrets fora do Git.
- **Ask first:** alterar auth/JWT/CORS, adicionar handlers de upload, modificar throttling, alterar dimensão de embeddings, adicionar dependências principais, alterar schema já utilizado, modificar CI/CD ou remover requisito obrigatório.
- **Never:** commitar chaves, guardar tokens em localStorage, remover testes para obter sucesso, ignorar isolamento, inventar citações, executar saída do LLM ou hardcodar resultados da demo.

## Success Criteria

- O fluxo completo executa localmente via Docker Compose.
- Upload não bloqueia a requisição HTTP e chega a `PROCESSED` ou `FAILED`.
- Busca retorna chunks relevantes filtrados pelo tenant.
- Toda resposta factual do RAG contém citação de página e trecho.
- Perguntas sem evidência são respondidas como não encontradas no contexto.
- Usuário de uma empresa não acessa editais de outra.
- Busca repetida utiliza Redis.
- Lint, testes e build passam em CI.

## Embeddings — decisão registrada

- **Provedor padrão:** local, modelo `intfloat/multilingual-e5-base`, CPU, 768D.
- **Preprocessamento:** documentos recebem `passage:`, consultas recebem
  `query:`; vetores são normalizados por norma L2, gerados em batch e
  reutilizados por cache local do modelo.
- **Identidade:** cada chunk persiste provider, modelo, revisão, dimensão,
  normalização e fingerprint. O retrieval exige a identidade completa; troca
  de modelo ou preprocessing exige reindexação explícita.
- **Reindexação:** `reindex_embeddings` usa staging corpus-wide, promoção
  transacional e mantém gerações antigas para rollback. Não há fallback
  silencioso para embeddings externos.
- **Compatibilidade pgvector:** `VectorField(dimensions=768)` e índice HNSW com
  operador de distância cosseno.
- **Providers legados:** Gemini/OpenRouter continuam no código para migração,
  mas só entram em operação quando `EMBEDDING_PROVIDER` os seleciona.

Fontes oficiais:

- https://opencode.ai/docs/zen
- https://huggingface.co/intfloat/multilingual-e5-base
- https://github.com/pgvector/pgvector-python#django

## Open Questions

- O storage local será suficiente para a demo ou haverá bucket compatível com S3?
- O deploy final será Cloud Run ou Render?
