# Spec: tender-management

## Objective

Registrar editais, aceitar PDFs e expor seu ciclo de vida por API.

## Acceptance Criteria

- Upload aceita PDF dentro do limite configurado e cria `PENDING`.
- Arquivos inválidos retornam `400`.
- CRUD filtra por empresa.
- Status e metadados são consultáveis.
- PDF é persistido por `storage_key` em volume privado `/var/lib/govintel/uploads` no MVP, atrás de um adapter que poderá usar S3.
- Download/remoção do PDF exige autorização do tenant e cleanup remove o blob associado.

## Boundary

Não coleta editais de portais externos nem implementa OCR.

## Storage and retention

O worker lê o arquivo pelo `storage_key`, nunca pelo nome original. O PDF não é servido por URL pública. Retenção de demo é configurável (padrão 30 dias); exclusão deve remover arquivo, chunks, cache e conversas relacionadas.

## Verification

Testar upload válido, corrompido, duplicado e acesso cross-tenant.
