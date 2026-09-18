# Spec: cache-protection

## Objective

Reduzir custo e proteger endpoints com Redis.

## Acceptance Criteria

- Busca repetida usa chave composta por tenant, query e filtros.
- Cache não cruza empresas.
- Novo processamento invalida resultados afetados.
- Login, busca e chat têm throttling e retornam `429` quando excedidos.
