import pytest
from django.core.exceptions import ValidationError

from apps.conversations.models import Conversation, Message
from apps.core.models import Company, User
from apps.tenders.models import Tender

pytestmark = pytest.mark.django_db


@pytest.fixture
def company_a():
    return Company.objects.create(name="Tenant Alpha")


@pytest.fixture
def company_b():
    return Company.objects.create(name="Tenant Beta")


@pytest.fixture
def user_a(company_a):
    return User.objects.create_user(
        email="alpha@tenant.com",
        password="Password123!",
        company=company_a,
    )


@pytest.fixture
def user_b(company_b):
    return User.objects.create_user(
        email="beta@tenant.com",
        password="Password123!",
        company=company_b,
    )


@pytest.fixture
def processed_tender_a(company_a):
    return Tender.objects.create(
        company=company_a,
        title="Edital Processado Alpha",
        status="PROCESSED",
    )


@pytest.fixture
def pending_tender_a(company_a):
    return Tender.objects.create(
        company=company_a,
        title="Edital Pendente Alpha",
        status="PENDING",
    )


def test_conversation_created_with_processed_tender(company_a, user_a, processed_tender_a):
    conversation = Conversation.objects.create(
        company=company_a,
        user=user_a,
        tender=processed_tender_a,
        title="Dúvidas sobre o Edital",
    )
    assert conversation.id is not None
    assert conversation.company == company_a
    assert conversation.user == user_a
    assert conversation.tender == processed_tender_a
    assert conversation.title == "Dúvidas sobre o Edital"


def test_conversation_rejects_non_processed_tender(company_a, user_a, pending_tender_a):
    with pytest.raises(ValidationError, match="PROCESSED"):
        conv = Conversation(
            company=company_a,
            user=user_a,
            tender=pending_tender_a,
        )
        conv.full_clean()
        conv.save()


def test_conversation_rejects_cross_tenant_tender(company_a, company_b, user_a):
    tender_b = Tender.objects.create(
        company=company_b,
        title="Edital Beta",
        status="PROCESSED",
    )
    with pytest.raises(ValidationError, match="mesma empresa"):
        conv = Conversation(
            company=company_a,
            user=user_a,
            tender=tender_b,
        )
        conv.full_clean()
        conv.save()


def test_messages_preserve_chronological_order_and_role(company_a, user_a, processed_tender_a):
    conv = Conversation.objects.create(
        company=company_a,
        user=user_a,
        tender=processed_tender_a,
    )

    m1 = Message.objects.create(
        conversation=conv,
        role="user",
        content="Qual o prazo de entrega?",
    )
    m2 = Message.objects.create(
        conversation=conv,
        role="assistant",
        content="O prazo de entrega é de 15 dias corridos.",
        citations=[
            {
                "chunkId": "11111111-1111-1111-1111-111111111111",
                "pageNumber": 2,
                "quote": "prazo de entrega é de 15 dias corridos",
                "score": 0.95,
            }
        ],
    )

    messages = list(conv.messages.all())
    assert len(messages) == 2
    assert messages[0].id == m1.id
    assert messages[0].role == "user"
    assert messages[1].id == m2.id
    assert messages[1].role == "assistant"
    assert len(messages[1].citations) == 1
    assert messages[1].citations[0]["pageNumber"] == 2


def test_conversation_strict_cross_tenant_isolation(
    company_a, company_b, user_a, user_b, processed_tender_a
):
    tender_b = Tender.objects.create(
        company=company_b,
        title="Edital Processado Beta",
        status="PROCESSED",
    )
    conv_a = Conversation.objects.create(
        company=company_a,
        user=user_a,
        tender=processed_tender_a,
    )
    conv_b = Conversation.objects.create(
        company=company_b,
        user=user_b,
        tender=tender_b,
    )

    a_conversations = Conversation.objects.filter(company=company_a)
    assert conv_a in a_conversations
    assert conv_b not in a_conversations


def test_conversation_serializer_formats_in_camel_case(company_a, user_a, processed_tender_a):
    from apps.conversations.serializers import ConversationPublicSerializer

    conv = Conversation.objects.create(
        company=company_a,
        user=user_a,
        tender=processed_tender_a,
        title="Conversa Serializer",
    )
    Message.objects.create(
        conversation=conv,
        role="user",
        content="Mensagem 1",
    )
    Message.objects.create(
        conversation=conv,
        role="assistant",
        content="Resposta 1",
        citations=[{"chunkId": "123", "pageNumber": 1, "quote": "trecho", "score": 0.9}],
    )

    serializer = ConversationPublicSerializer(conv)
    data = serializer.data

    assert data["id"] == str(conv.id)
    assert data["tenderId"] == str(processed_tender_a.id)
    assert data["title"] == "Conversa Serializer"
    assert "createdAt" in data
    assert "updatedAt" in data
    assert len(data["messages"]) == 2
    assert data["messages"][0]["role"] == "user"
    assert data["messages"][1]["role"] == "assistant"
    assert "conversationId" in data["messages"][0]
    assert "createdAt" in data["messages"][0]

