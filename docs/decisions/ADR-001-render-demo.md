# ADR-001: Render como alvo de preparação da demonstração

## Status

Accepted for deployment preparation; production deployment not authorized.

## Date

2026-09-17

## Context

O MVP precisa de uma plataforma demonstrável que execute imagens Docker, API
Django, worker Celery, PostgreSQL com pgvector, Redis e RabbitMQ. O ambiente
local já usa Compose e precisa continuar reproduzível. O repositório não tem
remoto Git configurado, portanto esta decisão deve preparar a operação sem
publicar infraestrutura.

## Decision

Preparar o deploy no Render com Web Services para Next.js e Django, Background
Worker para Celery, Postgres gerenciado com `vector`, Key Value compatível com
Redis e um Private Service Docker para RabbitMQ. Secrets ficam no painel ou em
Environment Groups. Health check da API é `/health/`; smoke test cobre API,
frontend e o fluxo crítico.

## Alternatives considered

### Kubernetes gerenciado

Rejeitado para a demonstração: adiciona cluster, ingress, secret manager e
observabilidade antes de validar o fluxo de produto.

### Manter somente Docker Compose

Mantido como ambiente local e fallback de desenvolvimento, mas não oferece
URL pública, rollback de serviço nem datastores gerenciados.

## Consequences

- As imagens são reutilizadas entre Compose e Render, com `PORT` configurável.
- O rollback de código pode reutilizar um artefato anterior, mas discos e
  configurações compartilhadas têm regras próprias do provedor.
- O volume local de uploads não pode ser compartilhado diretamente entre API e
  worker em serviços separados; um storage S3-compatible privado é pré-requisito
  para produção.
- Não há deploy automático nem secrets neste repositório; a publicação exige
  revisão e autorização posteriores.
