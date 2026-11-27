from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.api.v1.routes import get_agent, get_cache_service, get_rfb_client
from app.core.errors import LLMProviderError
from app.main import create_app
from app.services.openai_agent import AgentResponse


def test_chat_endpoint_returns_agent_response() -> None:
    app = create_app()
    mock_agent = AsyncMock()
    mock_agent.process_message.return_value = AgentResponse(
        reply="CBS calculada: R$ 35,20.",
        session_id="a" * 32,
        in_scope=True,
        pii_redacted_count=1,
        tool_executions=[{"tool": "simular_regime_regular", "output": {"objetos": []}}],
    )

    mock_cache = AsyncMock()
    mock_cache.check_rate_limit.return_value = True
    mock_cache.get_session.return_value = None

    app.dependency_overrides[get_agent] = lambda: mock_agent
    app.dependency_overrides[get_cache_service] = lambda: mock_cache

    client = TestClient(app)
    resp = client.post("/api/v1/chat", json={"message": "Simule curso de 1000 reais"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == "a" * 32
    assert data["pii_redacted_count"] == 1
    assert data["tools_used"] == [{"tool": "simular_regime_regular", "status": "ok"}]


def test_chat_endpoint_returns_429_when_rate_limited() -> None:
    app = create_app()
    mock_cache = AsyncMock()
    mock_cache.check_rate_limit.return_value = False
    app.dependency_overrides[get_cache_service] = lambda: mock_cache

    client = TestClient(app)
    resp = client.post("/api/v1/chat", json={"message": "Simule curso"})

    assert resp.status_code == 429


def test_chat_endpoint_returns_502_on_llm_provider_error() -> None:
    app = create_app()
    mock_agent = AsyncMock()
    mock_agent.process_message.side_effect = LLMProviderError("Timeout no provedor")

    mock_cache = AsyncMock()
    mock_cache.check_rate_limit.return_value = True

    app.dependency_overrides[get_agent] = lambda: mock_agent
    app.dependency_overrides[get_cache_service] = lambda: mock_cache

    client = TestClient(app)
    resp = client.post("/api/v1/chat", json={"message": "Simule curso"})

    assert resp.status_code == 502


def test_danfse_generate_and_download_flow() -> None:
    app = create_app()
    fake_pdf = b"%PDF-1.7-teste"

    mock_rfb = AsyncMock()
    mock_rfb.gerar_danfse_pdf.return_value = fake_pdf

    mock_cache = AsyncMock()
    mock_cache.check_rate_limit.return_value = True
    mock_cache.get_danfse_pdf.return_value = fake_pdf

    app.dependency_overrides[get_rfb_client] = lambda: mock_rfb
    app.dependency_overrides[get_cache_service] = lambda: mock_cache

    client = TestClient(app)
    gen_resp = client.post(
        "/api/v1/danfse", json={"xml_nfse": "<NFSe><infNFSe/></NFSe>"}
    )
    assert gen_resp.status_code == 200
    token = gen_resp.json()["download_token"]

    dl_resp = client.get(f"/api/v1/danfse/{token}")
    assert dl_resp.status_code == 200
    assert dl_resp.headers["content-type"] == "application/pdf"
    assert dl_resp.headers["cache-control"] == "no-store"
    assert dl_resp.content == fake_pdf
