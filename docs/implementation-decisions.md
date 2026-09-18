# Decisões de implementação

## 2026-09-16 — dependência circular no scaffold

Conflito entre `tasks/todo.md` (Task 1 exige seis serviços executando antes
das Tasks 2–3) e `docs/ci-cd-contract.md` (health real da API/worker/frontend).
As aplicações/Dockerfiles ainda não existem; não é possível verificar saúde
real antes de criar seus scaffolds.

Resolução: Task 1 declara os seis serviços, valida Compose e inicia os três
serviços de dados. Tasks 2–3 completam os runtimes da mesma capability;
o critério original de seis serviços saudáveis permanece pendente até o
checkpoint conjunto. Nenhuma capability de domínio avança antes desse gate.
Não usar servidores substitutos nem health checks incondicionais.

A autorização explícita do prompt cobre implementação local dos contratos.
Revisões previstas no plano não exigem reconfirmação para cada alteração já
autorizada; push, deploy e infraestrutura compartilhada continuam sujeitos a
aprovação explícita.

## Fontes oficiais consultadas

- Docker Compose 5.2.0 instalado: [startup e readiness](https://docs.docker.com/compose/how-tos/startup-order/).
- [Serviços, recursos, healthcheck e volumes](https://docs.docker.com/reference/compose-file/services/).
- [Interpolação e variáveis obrigatórias](https://docs.docker.com/reference/compose-file/interpolation/).
- [Imagem pgvector/PostgreSQL 16](https://github.com/pgvector/pgvector#docker).

Validação de YAML não comprova comportamento em execução. Evidências de
runtime serão registradas separadamente em context.md e tasks/todo.md.

## 2026-09-16 — exceção de enumeração no cadastro aprovada pelo usuário

Conflito: o prompt proíbe revelar existência de email, enquanto
SPEC-identity-tenant.md e Task 5 exigem HTTP 409 para email duplicado.
O usuário aprovou manter 409 genérico no cadastro do MVP. Essa diferença de
status permite inferir duplicidade e é uma exceção explícita e limitada.
Login/refresh não revelam existência, atividade ou motivo da rejeição.
Não adicionar confirmação de email nem alterar o fluxo de registro neste MVP.

## 2026-09-16 — dependências do scaffold web

Next.js 15.5.25 permanece obrigatório; Node 24.17.0 e npm lockfile.
Auditoria inicial encontrou PostCSS vulnerável transitivo de Next e
@vitest/mocker vulnerável transitivo de Vitest 3. Correção: override específico
de Next → PostCSS 8.5.28, dentro da major 8; Vitest 4.1.11.
Sem `audit fix --force`; scripts de instalação bloqueados em .npmrc.
`npm audit` após atualização: zero vulnerabilidades. Testes e build validam
compatibilidade. ESLint 9 é mantido pois eslint-config-next 15 declara suporte
até a major 9; atualização de major requer compatibilidade futura do Next 15.

Fontes:
- https://nextjs.org/docs/15/app/getting-started/installation
- https://nextjs.org/docs/15/app/guides/environment-variables
- https://github.com/postcss/postcss/security/advisories/GHSA-r28c-9q8g-f849
- https://github.com/postcss/postcss/releases
- https://github.com/vitest-dev/vitest/security/advisories/GHSA-82fw-gwwq-j7x9

## 2026-09-16 — contrato de sessão antes do schema

docs/api-contract.md dizia que toda rota exceto registro/login exigia access,
contradizendo refresh por cookie em SPEC-identity-tenant.md e no prompt.
A tabela também dizia “tokens” no registro, contradizendo refresh nunca em JSON.
Corrigido: refresh/logout usam cookie e CSRF/origin, /me usa Bearer; health e
bootstrap CSRF são públicos. Mutações de sessão validam CSRF e origem permitida.
Não introduzir auth.User provisório: User customizado e suas migrations serão
introduzidos juntos na Task 4.

Fontes: https://docs.djangoproject.com/en/5.2/topics/auth/customizing/;
https://django-rest-framework-simplejwt.readthedocs.io/en/stable/settings.html;
https://django-rest-framework-simplejwt.readthedocs.io/en/stable/blacklist_app.html.

## 2026-09-17 — atualização após auditoria e preparação de deploy

`pip-audit --strict` identificou advisories alcançáveis em DRF 3.16.1,
LangChain 0.3.30 e pypdf 5.9.0. As restrições foram elevadas para DRF 3.18.1,
LangChain 1.4.1 e pypdf 6.19.0; `uv.lock` foi regenerado e a suíte completa
permaneceu verde. A auditoria npm continuou sem findings. A atualização não
usa remediation automática nem ignora IDs.

Para entrega, Render foi escolhido como alvo de preparação e a justificativa,
as limitações de storage compartilhado, secrets, smoke test e rollback estão
em [ADR-001](decisions/ADR-001-render-demo.md) e
[docs/deployment.md](deployment.md). Nenhuma infraestrutura foi publicada.
