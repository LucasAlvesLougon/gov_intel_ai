# Spec: document-pipeline

## Objective

Processar PDFs de forma assíncrona usando RabbitMQ e Celery.

## Acceptance Criteria

- A API agenda task sem processar o PDF no ciclo HTTP.
- Worker registra `PROCESSING`, extrai texto por página, cria chunks e finaliza em `PROCESSED`.
- Exceções resultam em `FAILED` com retry limitado e mensagem segura.
- Cada chunk preserva página, índice e offsets.
- Chunks têm identidade determinística (`tender_id`, `pipeline_generation`, `chunk_index`, hash do texto normalizado) e upsert transacional.
- Nova geração começa como `STAGED`; a geração current anterior permanece visível durante o processamento.
- Somente após todos os chunks/embeddings persistirem com sucesso uma transação troca `current_generation` e marca a geração anterior como não-current.
- Falha, crash ou timeout descarta a geração staged e preserva a geração current anterior; cleanup remove gerações antigas segundo retenção configurada.
- Atualizações de estado usam compare-and-set por geração; task stale não pode sobrescrever resultado mais novo.
- O worker mantém lease/heartbeat e um reconciliador recupera jobs `PROCESSING` expirados.
- Publicação no broker usa outbox transacional; falha de RabbitMQ não deixa edital permanentemente `PENDING`.
- A fila é durável, possui retry limitado, dead-letter e política para poison messages.

## Parser limits

- Limitar bytes do arquivo, número de páginas e caracteres extraídos.
- Aplicar timeout e isolar falhas do parser; remover temporários em sucesso ou erro.
- PDFs criptografados, malformados ou sem texto terminam com códigos seguros como `PDF_INVALID`, `PDF_ENCRYPTED` ou `NO_TEXT_EXTRACTED`.
- Offsets são definidos como índices de code points sobre texto normalizado persistido no chunk.

## Verification

Testes com worker real no Compose e PDF textual de fixture.
