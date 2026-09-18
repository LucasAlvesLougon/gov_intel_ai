# Roteiro da demo

## Pré voo

Na raiz, confirme Docker Desktop e execute:

```text
docker compose config --quiet
docker compose -f docker-compose.yml -f docker-compose.e2e.yml up -d --build --wait
docker compose ps
curl http://localhost:8000/health/
```

O override E2E define `LLM_PROVIDER=mock` e `EMBEDDING_PROVIDER=mock`; embeddings ficam determinísticos,
o chat responde extrativamente a partir dos trechos encontrados e nada envia o
PDF para um provedor externo. Para usar
uma chave real, configure-a somente no secret manager do ambiente e remova o
override mockado. Nunca cole secrets no roteiro ou no terminal compartilhado.

## Fluxo visível

1. Abra `http://localhost:3000/register` (ou `http://127.0.0.1:3000/register`), informe uma empresa, um email de
   demonstração e uma senha temporária, e confirme o redirecionamento para o
   dashboard.
2. No dashboard, selecione o fixture
   [`e2e/fixtures/edital-demo.pdf`](../e2e/fixtures/edital-demo.pdf), preencha um
   título e envie. O retorno esperado é `202` e o card fica `PENDING`.
3. Mostre o polling do card: `PENDING` → `PROCESSING` → `PROCESSED`. Em
   paralelo, `docker compose logs -f worker` exibe somente eventos operacionais,
   sem tokens, prompts ou conteúdo integral do PDF.
4. Abra **Busca**, pesquise `prazo de execução` e mostre resultados com
   `score`, página e snippet. O filtro de edital aceita somente editais
   processados do tenant atual.
5. Abra **Chat** pelo resultado, pergunte `Qual é o prazo de execução?` e
   mostre a resposta com citação. A citação deve apontar para a página e para
   o trecho persistido no fixture.
6. Faça a mesma busca novamente para demonstrar o cache Redis. A resposta
   mantém os mesmos resultados; a invalidação ocorre quando um edital é
   processado ou removido.
7. Abra RabbitMQ Management em `http://localhost:15672` com as credenciais
   locais da `.env` e mostre a fila `govintel.pipeline`, a DLQ e o worker
   saudável. PostgreSQL e Redis aparecem em `docker compose ps`.

## Verificação automatizada

O fluxo completo pode ser repetido sem interação:

```text
npx playwright install chromium
npx playwright test e2e/govintel-flow.spec.ts
```

Se o teste falhar, consulte `playwright-report/` e `test-results/`; esses
artefatos são locais e estão no `.gitignore`. Ao terminar, use
`docker compose down` para parar o stack. Preserve os volumes durante uma
demo recorrente; `docker compose down -v` apaga o banco, as filas e os uploads.
