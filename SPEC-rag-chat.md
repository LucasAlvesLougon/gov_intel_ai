# Spec: rag-chat

## Objective

Responder perguntas sobre um edital utilizando apenas contexto recuperado e devolver citações rastreáveis.

## Acceptance Criteria

- Chat rejeita edital não processado.
- Retrieval fornece chunks ao prompt.
- Resposta inclui `chunk_id`, página, trecho e score.
- Quando não há evidência suficiente, informa a limitação.
- Conversas e mensagens ficam isoladas por empresa.
- A saída do LLM obedece schema estruturado e cada citation ID deve existir no conjunto de chunks recuperados.
- O quote devolvido é exatamente o texto persistido do chunk, após validação no backend.
- O prompt delimita documentos como dados não confiáveis e não disponibiliza ferramentas, URLs, shell ou execução de código.
- Limites de contexto, tokens, timeout, retry e falha do provedor são explícitos.

## Verification

Fixture com respostas conhecidas e teste que detecta citação de página incorreta.
