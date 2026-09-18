# Spec: web-application

## Objective

Expor uma demo navegável do fluxo completo em Next.js 15.

## Acceptance Criteria

- Usuário consegue registrar, entrar, enviar PDF e acompanhar polling de status.
- Dashboard lista editais do tenant.
- Busca e chat exibem loading, vazio, erro e citações.
- Refresh token mantém sessão sem expor secrets.

## Verification

Vitest para componentes e Playwright para o fluxo ponta a ponta.
