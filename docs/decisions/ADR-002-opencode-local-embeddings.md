# ADR-002 — OpenCode para LLM e embeddings locais

Data: 2026-09-18

## Decisão

Separar a configuração do LLM da configuração de embeddings. O padrão do chat
é OpenCode Zen via API OpenAI-compatible; o padrão de embeddings é
`intfloat/multilingual-e5-base` local, em CPU, com 768 dimensões. Cada vetor
usa `passage:` ou `query:`, normalização L2, batch configurável e um fingerprint
de modelo/revisão/preprocessamento persistido em `DocumentChunk`.

Providers Gemini/OpenRouter continuam disponíveis somente por seleção explícita.
Uma chave presente no ambiente não altera o provider escolhido e nenhuma falha
faz fallback silencioso.

## Reindexação e rollback

`reindex_embeddings` primeiro gera todos os chunks na próxima geração como
`staged`, valida metadata e cardinalidade e só depois promove o corpus em uma
transação. A geração anterior continua armazenada e não-current. Em falha, o
staging é removido e a busca permanece na geração anterior. O rollback explícito
reativa uma geração anterior por edital.

## Consequências

- PDFs não são enviados a um serviço externo para gerar embeddings.
- O primeiro uso precisa baixar e manter o modelo no volume privado compartilhado.
- CPU e memória passam a ser requisitos operacionais; API e worker usam um
  processo principal e limite de 2 GiB no Compose local.
- O endpoint OpenCode valida o modelo configurado no catálogo antes da geração;
  um modelo ausente produz erro seguro, sem alias implícito.

Referências oficiais: [OpenCode Zen](https://opencode.ai/docs/zen) e
[modelo multilingual-e5-base](https://huggingface.co/intfloat/multilingual-e5-base).
