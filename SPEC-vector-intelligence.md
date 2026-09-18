# Spec: vector-intelligence

## Objective

Gerar embeddings e executar busca semântica no PostgreSQL com pgvector/HNSW.

## Acceptance Criteria

- A dimensão do vetor é única, configurada como 768 e validada na inicialização.
- Chunks são persistidos com embedding e metadados.
- Busca filtra por tenant e edital opcional.
- Resultados incluem score, página e snippet.
- Cada embedding persiste `modelName`, `modelVersion`, `dimensions`, `normalization`, `preprocessingFingerprint` e `pipelineGeneration`.
- Troca de modelo ou preprocessing exige re-embedding explícito; embeddings de espaços diferentes nunca são comparados.
- Busca usa índice B-tree de tenant, overfetch configurável e teste de recall; dataset pequeno pode usar fallback exato para validação.

## Implementation Decision

Usar `intfloat/multilingual-e5-base` local em CPU, com saída de 768 dimensões.
Para documentos, prefixar `passage:`; para consultas, prefixar `query:`. Usar
`normalize_embeddings=True`, batch configurável e distância cosseno com
`HnswIndex` e `vector_cosine_ops`.

O modelo tem limite de 512 tokens; o chunker e o adapter devem evitar entrada
acima desse limite. O cache do modelo é privado e compartilhado apenas por API
e worker. Gemini/OpenRouter continuam como providers de migração, selecionados
explicitamente, sem mistura de metadata no retrieval.

## Retrieval correctness

O repositório deve buscar com filtro de `company_id` e `is_current=true`, ordenar por distância cosseno e usar overfetch iterativo limitado. `topK` aceita no máximo 50 e a paginação usa `page`/`pageSize` com `pageSize` máximo 50. Se a quantidade válida ficar abaixo de `topK` ou do limiar de recall, executar fallback exato no mesmo tenant. O teste deve cobrir tenant pequeno, tenant enviesado e tenant sem chunks.

## Migration policy

Adicionar `embedding_model_version`, `embedding_dimensions`, `normalization` e `preprocessing_fingerprint` ao chunk. Uma alteração incompatível cria uma migration/reindexação versionada; não reutilizar a coluna antiga silenciosamente.

## Sources

- https://huggingface.co/intfloat/multilingual-e5-base
- https://github.com/pgvector/pgvector-python#django
- https://opencode.ai/docs/zen
