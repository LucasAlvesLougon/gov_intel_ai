def test_opencode_rag_retries_once_then_accepts_only_literal_citation():
    from apps.conversations.rag_service import OpenCodeRAGService

    chunk_id = "11111111-1111-1111-1111-111111111111"
    tender_id = "22222222-2222-2222-2222-222222222222"
    retrieved = [
        {
            "chunkId": chunk_id,
            "tenderId": tender_id,
            "pageNumber": 3,
            "startCharOffset": 100,
            "endCharOffset": 130,
            "text": "O prazo de entrega é de 30 dias.",
            "score": 0.9,
        }
    ]

    class FakeAdapter:
        calls = 0

        def generate_json(self, system_prompt, user_prompt):
            self.calls += 1
            quote = "inventada" if self.calls == 1 else "O prazo de entrega é de 30 dias."
            return {
                "answer": "Resposta fundamentada",
                "citations": [
                    {
                        "documentId": tender_id,
                        "chunkId": chunk_id,
                        "pageNumber": 3,
                        "quote": quote,
                    }
                ],
            }

    adapter = FakeAdapter()
    result = OpenCodeRAGService(adapter=adapter).answer(
        company=None,
        tender=None,
        user_query="Qual é o prazo?",
        retrieved_chunks=retrieved,
    )

    assert adapter.calls == 2
    assert result["answer"] == "Resposta fundamentada"
    assert result["citations"][0]["documentId"] == tender_id
    assert result["citations"][0]["quote"] == "O prazo de entrega é de 30 dias."


def test_opencode_rag_rejects_invalid_json_shape_without_fallback_to_mock():
    from apps.conversations.rag_service import OpenCodeRAGService

    class FakeAdapter:
        def generate_json(self, system_prompt, user_prompt):
            return {"answer": "não validada", "citations": {}}

    result = OpenCodeRAGService(adapter=FakeAdapter()).answer(
        company=None,
        tender=None,
        user_query="Pergunta",
        retrieved_chunks=[
            {
                "chunkId": "chunk",
                "tenderId": "tender",
                "pageNumber": 1,
                "text": "Texto.",
                "score": 0.9,
            }
        ],
    )

    assert result["citations"] == []
    assert "evidências suficientes" in result["answer"]
